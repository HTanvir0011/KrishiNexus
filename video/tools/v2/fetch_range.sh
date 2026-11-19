#!/usr/bin/env bash
# Fetch bytes [start, end] of one ResembleAI/chatterbox file into <file>.r<k>, resuming through drops, so a large file
# can come down over several connections: fetch_range.sh s3gen.safetensors 0 0 352161539 & ...; then concatenate
# the .r* parts in order and check the SHA-256 from the Hugging Face API. Only 206 (partial content) replies are
# appended, so a server that ignores the range can't corrupt the part.
dir=/c/ai-congress/KrishiNexus/video/models/chatterbox
f=$1; k=$2; start=$3; end=$4
want=$((end - start + 1))
out="$dir/$f.r$k"
for i in $(seq 1 1000); do
  have=$(stat -c %s "$out" 2>/dev/null || echo 0)
  [ "$have" -eq "$want" ] && { echo "ok $f part $k"; exit 0; }
  [ "$have" -gt "$want" ] && { echo "part $k too long"; exit 2; }
  code=$(curl -sS -L --connect-timeout 30 -y 60 -Y 2000 -r "$((start + have))-$end" -o "$out.tmp" \
    -w "%{http_code}" "https://huggingface.co/ResembleAI/chatterbox/resolve/main/$f")
  [ "$code" = "206" ] && [ -s "$out.tmp" ] && cat "$out.tmp" >> "$out"
  rm -f "$out.tmp"
  sleep 3
done
exit 1
