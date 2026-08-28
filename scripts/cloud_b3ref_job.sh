#!/bin/bash
# Pipeline B — Eixo B3: vídeo-nativo (Pegasus 1.2) sobre o vídeo principal em clipes de 60s.
# Instância CPU. AUTO-TERMINA. Saídas: s3://$BUCKET/runs/b3ref/.
set -euo pipefail
exec > /var/log/tcc-b3.log 2>&1

BUCKET=video-analytics-store
REGION=us-east-1
echo "=== TCC B3 job (Pegasus no VIDEO DE REFERENCIA p/ eval IHO): $(date -u) ==="
apt-get update -q && apt-get install -y -q ffmpeg zip python3-venv python3-pip unzip curl
command -v aws >/dev/null || { curl -sS https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscli.zip && unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install; }

WORK=/opt/tcc && mkdir -p $WORK && cd $WORK
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip boto3

aws s3 cp s3://$BUCKET/videos/derived/ref_5fps.mp4 ref_5fps.mp4 --region $REGION --only-show-errors

# corta em clipes de 60s e sobe para o S3 (Pegasus lê por S3 URI)
mkdir -p clips
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 ref_5fps.mp4 | cut -d. -f1)
N=$(( (DUR + 59) / 60 ))
for i in $(seq 0 $((N - 1))); do
  ffmpeg -v error -ss $((i * 60)) -t 60 -i ref_5fps.mp4 -c copy "clips/c$(printf %03d $i).mp4" -y
done
aws s3 sync clips "s3://$BUCKET/pipeline-b/b3ref_clips/" --region $REGION --only-show-errors
echo "clipes: $N"

cat > run_b3.py <<PYEOF
import json, time, boto3, botocore

N = $N
SCHEMA = {
    "type": "object",
    "properties": {
        "counts_at_instants": {"type": "array", "description": "Pessoas visiveis aos 0s,10s,20s,30s,40s,50s (6 inteiros)",
                               "items": {"type": "integer"}},
        "unique_people": {"type": "integer", "description": "Pessoas DISTINTAS no clipe inteiro"},
        "interactions": {"type": "array", "items": {"type": "object", "properties": {
            "t_seconds": {"type": "number"},
            "action": {"type": "string", "enum": ["pegando_produto", "devolvendo_produto", "examinando_produto"]},
            "description": {"type": "string"}}, "required": ["t_seconds", "action"]}},
    },
    "required": ["counts_at_instants", "unique_people", "interactions"],
}
PROMPT = ("Voce analisa video de camera de seguranca de loja de vestuario. Responda em JSON: "
          "1) counts_at_instants: quantas pessoas estao visiveis exatamente aos 0s, 10s, 20s, 30s, 40s e 50s; "
          "2) unique_people: quantas pessoas DISTINTAS aparecem no clipe inteiro (nao some recontagens); "
          "3) interactions: eventos de cliente pegando/devolvendo/examinando produto, com instante aproximado.")

rt = boto3.client("bedrock-runtime", region_name="us-east-1",
                  config=botocore.config.Config(read_timeout=180, retries={"max_attempts": 4}))
results = []
t_all = time.time()
for i in range(N):
    uri = f"s3://video-analytics-store/pipeline-b/b3ref_clips/c{i:03d}.mp4"
    t0 = time.time()
    try:
        resp = rt.invoke_model(modelId="twelvelabs.pegasus-1-2-v1:0", body=json.dumps({
            "inputPrompt": PROMPT,
            "mediaSource": {"s3Location": {"uri": uri, "bucketOwner": "522681761216"}},
            "responseFormat": {"jsonSchema": SCHEMA},
        }))
        body = json.loads(resp["body"].read())
        data = json.loads(body["message"])
        results.append({"clip": i, "t_start": i * 60, "ok": True, "wall_s": round(time.time() - t0, 1),
                        "result": data})
        print(f"clip {i}: ok {results[-1]['wall_s']}s counts={data['counts_at_instants']} uniq={data['unique_people']} inter={len(data['interactions'])}", flush=True)
    except Exception as e:
        results.append({"clip": i, "t_start": i * 60, "ok": False, "error": str(e)[:250]})
        print(f"clip {i}: ERRO {str(e)[:120]}", flush=True)
json.dump({"n_clips": N, "wall_total_s": round(time.time() - t_all, 1), "clips": results},
          open("b3_results.json", "w"), ensure_ascii=False, indent=1)
PYEOF
./venv/bin/python run_b3.py

aws s3 cp b3_results.json s3://$BUCKET/runs/b3ref/b3_results.json --region $REGION --only-show-errors
aws s3 cp /var/log/tcc-b3.log s3://$BUCKET/runs/b3ref/job_log.txt --region $REGION --only-show-errors || true
echo "=== done: $(date -u) — shutting down ==="
shutdown -h now
