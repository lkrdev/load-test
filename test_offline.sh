#!/bin/bash

# Ensure required environment variables are set
if [ -z "$LOOKERSDK_BASE_URL" ] || [ -z "$LOOKERSDK_CLIENT_ID" ] || [ -z "$LOOKERSDK_CLIENT_SECRET" ]; then
  echo "Error: LOOKERSDK_BASE_URL, LOOKERSDK_CLIENT_ID, and LOOKERSDK_CLIENT_SECRET must be set."
  exit 1
fi

# Extract the hostname from the Looker Base URL
LOOKER_HOST=$(python3 -c "from urllib.parse import urlparse; print(urlparse('$LOOKERSDK_BASE_URL').hostname)")
# Resolve the Looker Host to an IP address
LOOKER_IP=$(python3 -c "import socket; print(socket.gethostbyname('$LOOKER_HOST'))")

echo "===================================================="
echo "Looker Host: $LOOKER_HOST"
echo "Looker IP:   $LOOKER_IP"
echo "===================================================="

# Build the offline Dockerfile
echo "Building Dockerfile.offline..."
docker build -t lkr-load-test:offline -f Dockerfile.offline .

# Function to run the container
run_container() {
  USE_PATCH=$1
  # Read from environment or use placeholders
  QUERY_ID="${QUERY_ID:-YOUR_QUERY_ID}"
  MODEL="${MODEL:-YOUR_MODEL}"
  
  if [ "$USE_PATCH" = "true" ]; then
    START_COMMAND="lkr --gevent-patch load-test query --query=$QUERY_ID --users=5 --spawn-rate=1 --run-time=1 --model=$MODEL"
    echo ">>> Running WITH gevent patch..."
  else
    START_COMMAND="lkr load-test query --query=$QUERY_ID --users=5 --spawn-rate=1 --run-time=1 --model=$MODEL"
    echo ">>> Running WITHOUT gevent patch..."
  fi

  docker run --rm -it \
    --cap-add=NET_ADMIN \
    -e LOOKERSDK_BASE_URL="$LOOKERSDK_BASE_URL" \
    -e LOOKERSDK_CLIENT_ID="$LOOKERSDK_CLIENT_ID" \
    -e LOOKERSDK_CLIENT_SECRET="$LOOKERSDK_CLIENT_SECRET" \
    -e SE_OFFLINE=true \
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
      
      # Drop everything else
      iptables -A OUTPUT -j DROP
      
      echo 'Testing internet isolation (should time out)...'
      curl --connect-timeout 3 https://google.com || echo 'Internet access blocked successfully.'
      
      echo 'Executing load test...'
      $START_COMMAND
    "
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
