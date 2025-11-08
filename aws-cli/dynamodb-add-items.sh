aws dynamodb put-item \
    --table-name myGame \
    --item \
        '{"playerUSERNAME": {"S": "billy@example.com"}, 
            "playerID": {"N": "000000001"}, 
            "inGameCurrency": {"N": "500"}, 
            "MapID": {"N": "1"}, 
            "RegionID": {"N": "1"}, 
            "PlayerLEVEL": {"N": "5"}, 
            "PrimaryWeapon": {"S": "BasicSword"}, 
            "SecondaryWeapon": {"S": "BasicDagger"}, 
            "Armor": {"S": "BasicCloth"}, 
            "ArmorSkin": {"S": "StartingSkin1"}, 
            "PowerUps": {"S": "NullBoost"}, 
            "PresentLocation": {"S": "Shire"}}'
