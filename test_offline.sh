#!/bin/bash

# Load environment variables from .env if it exists
if [ -f .env ]; then
  _SE_OFFLINE="$SE_OFFLINE"
  set -a
  . .env
  set +a
  if [ -n "$_SE_OFFLINE" ]; then
    SE_OFFLINE="$_SE_OFFLINE"
  fi
fi

# Ensure required environment variables are set
if [ -z "$LOOKERSDK_BASE_URL" ] || [ -z "$LOOKERSDK_CLIENT_ID" ] || [ -z "$LOOKERSDK_CLIENT_SECRET" ]; then
  echo "Error: LOOKERSDK_BASE_URL, LOOKERSDK_CLIENT_ID, and LOOKERSDK_CLIENT_SECRET must be set."
  exit 1
fi

# Extract the hostname from the Looker Base URL
LOOKER_HOST=$(python3 -c "from urllib.parse import urlparse; print(urlparse('$LOOKERSDK_BASE_URL').hostname)")
# Resolve the Looker Host to an IP address
LOOKER_IP=$(python3 -c "import socket; print(socket.gethostbyname('$LOOKER_HOST'))")

# Resolve CDN hosts
CDNS=("static-a.lookercdn.com" "static-b.lookercdn.com" "static-a.cdn.looker.app")
CDN_IPS=()

echo "===================================================="
echo "Looker Host: $LOOKER_HOST"
echo "Looker IP:   $LOOKER_IP"

for cdn in "${CDNS[@]}"; do
  ip=$(python3 -c "import socket; print(socket.gethostbyname('$cdn'))")
  CDN_IPS+=("$ip")
  echo "CDN $cdn IP: $ip"
done

echo "===================================================="

CDN_RULES="      # Allow CDNs"$'\n'
for i in "${!CDNS[@]}"; do
  CDN_RULES+="      # ${CDNS[$i]}"$'\n'
  CDN_RULES+="      iptables -A OUTPUT -d ${CDN_IPS[$i]} -j ACCEPT"$'\n'
done

# Build the offline Dockerfile
echo "Building Dockerfile.offline..."
docker build -t lkr-load-test:offline -f Dockerfile.offline .

# Function to run the container
run_container() {
  USE_PATCH=$1
  # Read from environment or use placeholders
  QUERY_ID="${QUERY_ID:-YOUR_QUERY_ID}"
  MODEL="${MODEL:-YOUR_MODEL}"
  
  PORT_ARGS=""
  if [ -n "$DASHBOARD_ID" ]; then
    PORT_ARGS="-p 4000:4000"
    if [ "$USE_PATCH" = "true" ]; then
      START_COMMAND="lkr load-test embed-observability --dashboard=$DASHBOARD_ID --users=5 --spawn-rate=1 --run-time=1 --model=$MODEL --debug"
      echo ">>> Running embed-observability test WITH gevent patch..."
    else
      START_COMMAND="lkr --no-gevent-patch load-test embed-observability --dashboard=$DASHBOARD_ID --users=5 --spawn-rate=1 --run-time=1 --model=$MODEL --debug"
      echo ">>> Running embed-observability test WITHOUT gevent patch..."
    fi
  else
    if [ "$USE_PATCH" = "true" ]; then
      START_COMMAND="lkr load-test query --query=$QUERY_ID --users=5 --spawn-rate=1 --run-time=1 --model=$MODEL"
      echo ">>> Running query test WITH gevent patch..."
    else
      START_COMMAND="lkr --no-gevent-patch load-test query --query=$QUERY_ID --users=5 --spawn-rate=1 --run-time=1 --model=$MODEL"
      echo ">>> Running query test WITHOUT gevent patch..."
    fi
  fi

  echo "Generated CDN Rules:"
  echo "$CDN_RULES"

  mkdir -p tmp/log
  LOG_FILE="tmp/log/$(date +"%Y%m%dT%T")_$(python3 -c 'import uuid; print(uuid.uuid4())')_log.txt"
  echo ">>> Saving execution logs to: $LOG_FILE"

  docker run --rm -i $PORT_ARGS \
    --cap-add=NET_ADMIN \
    -e LOOKERSDK_BASE_URL="$LOOKERSDK_BASE_URL" \
    -e LOOKERSDK_CLIENT_ID="$LOOKERSDK_CLIENT_ID" \
    -e LOOKERSDK_CLIENT_SECRET="$LOOKERSDK_CLIENT_SECRET" \
    -e SE_OFFLINE="${SE_OFFLINE:-true}" \
    -e SE_AVOID_STATS="${SE_AVOID_STATS:-true}" \
    -e PYTHONUNBUFFERED=1 \
    lkr-load-test:offline \
    /bin/sh -c "
      echo 'Applying firewall rules...'
      # Allow loopback
      iptables -A OUTPUT -o lo -j ACCEPT
      
      # Allow DNS
      iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
      iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
      
      # Allow Looker IP
      iptables -A OUTPUT -d $LOOKER_IP -j ACCEPT
      
$CDN_RULES
      
      # Reject everything else
      iptables -A OUTPUT -j REJECT
      
      echo 'Testing internet isolation (should time out)...'
      curl --connect-timeout 3 https://google.com || echo 'Internet access blocked successfully.'
      
      echo 'Executing load test...'
      $START_COMMAND
    " 2>&1 | tee "$LOG_FILE"
}

# Check arguments
if [ "$1" = "with-patch" ]; then
  run_container "true"
elif [ "$1" = "without-patch" ]; then
  run_container "false"
else
  echo "----------------------------------------------------"
  echo "Usage:"
  echo "  To run WITHOUT gevent patch:"
  echo "    ./test_offline.sh without-patch"
  echo ""
  echo "  To run WITH gevent patch:"
  echo "    ./test_offline.sh with-patch"
  echo "----------------------------------------------------"
fi
