export DEPLOY_ENV=dev
export NIFI_API_ENDPOINT=http://127.0.0.1:8082/nifi-api/
export NIFI_BUCKET=MONITORING
export NIFI_PROCESS=myProcessGroup


echo "on environment $DEPLOY_ENV"

echo "using endpoint: $NIFI_API_ENDPOINT"

BUCKET_ID=$(curl -k $(echo $NIFI_API_ENDPOINT)/buckets/ | python3 get_nifi_values.py bucket $(echo $NIFI_BUCKET))
echo "bucket id:"
echo $BUCKET_ID

FLOW_ID=$(curl -k $(echo $NIFI_API_ENDPOINT)/buckets/$BUCKET_ID/flows | python3 get_nifi_values.py flow $(echo $NIFI_PROCESS))

echo "flow id: "
echo $FLOW_ID

mkdir -p ./nifi/configurations/$DEPLOY_ENV

curl -k $(echo $NIFI_API_ENDPOINT)/buckets/$BUCKET_ID/flows/$FLOW_ID/versions/latest | python3 get_nifi_values.py clean $(echo $NIFI_PROCESS)  $(echo $DEPLOY_ENV)
