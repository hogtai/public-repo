aws dynamodb create-table \
    --table-name myGame \
    --attribute-definitions \
        AttributeName=playerUSERNAME,AttributeType=S \
        AttributeName=playerID,AttributeType=N \
    --key-schema \
        AttributeName=playerUSERNAME,KeyType=HASH \
        AttributeName=playerID,KeyType=RANGE \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5
