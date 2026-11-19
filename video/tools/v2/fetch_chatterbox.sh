#!/usr/bin/env bash
# Fetch one ResembleAI/chatterbox file into video/models/chatterbox/ with curl, resuming through network drops (the
# Hugging Face Xet client stalled on this connection). Run one per file, in parallel:
#   fetch_chatterbox.sh s3gen.safetensors 1056484620 & fetch_chatterbox.sh t3_cfg.pt 1064892246
# t3_cfg.pt is the half-size checkpoint of t3_cfg.safetensors; clone.py converts it (the connection was ~250 kB/s).
dir=/c/ai-congress/KrishiNexus/video/models/chatterbox
f=$1; want=$2
mkdir -p "$dir"
for i in $(seq 1 1000); do
  [ "$(stat -c %s "$dir/$f" 2>/dev/null || echo 0)" = "$want" ] && { echo "ok $f"; exit 0; }
  curl -sS -L -C - --connect-timeout 30 -y 60 -Y 2000 -o "$dir/$f.part" "https://huggingface.co/ResembleAI/chatterbox/resolve/main/$f"
  have=$(stat -c %s "$dir/$f.part" 2>/dev/null || echo 0)
  if [ "$have" = "$want" ]; then mv "$dir/$f.part" "$dir/$f"; else echo "retry $i $f at $have"; sleep 5; fi
done
exit 1
