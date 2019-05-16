#!/bin/sh

echo "Starting Server Encryption"

echo "Starting process to enable SSL encryption"
#Two different files in the server need to be created. 'server.crt' (public) & 'server.key' (private)

echo "Step 1 of generating keypair - generating a request"
#change -subj if you want different information for the certificate
#change -passout if you want a different
sudo openssl req -new -text -out server.req -subj "/C=US/ST=Virginia/L=Blacksburg/O=Global Security/OU=IT Department/CN=example.com" -passout pass:hello

echo "Step 2, removing passphrase"

#-passin pass == -passout pass (last step)
sudo openssl rsa -in privkey.pem -out server.key -passin pass:hello

echo "Step 3 is to remove privkey.pem because there exists an RSA version in server.key"
sudo rm -f privkey.pem

echo "Step 4, generate self signed certificate"
sudo openssl req -x509 -in server.req -text -key server.key -out server.crt

#moving server.key, server.req, and server.crt to /var/lib/pgsql/data because postgresql looks there for keys and certs
echo "Moving server.key, server.req, and server.crt to /var/lib/pgsql/data"
sudo mv server.req /var/lib/pgsql/data && sudo mv server.key /var/lib/pgsql/data && sudo mv server.crt /var/lib/pgsql/data

echo "Step 5"
sudo chown postgres /var/lib/pgsql/data/server.key && sudo chmod 600 /var/lib/pgsql/data/server.key

echo "Step 6, modifying postgresql.conf"
sudo sed -i 's/#password_encryption/password_encryption/g ' /var/lib/pgsql/data/postgresql.conf  #uncomment password_encryption
sudo sed -i 's/#ssl/ssl/g ' /var/lib/pgsql/data/postgresql.conf  #uncomment ssl
sudo sed -i '/ssl/ s/'off'/'on'/g' /var/lib/pgsql/data/postgresql.conf #change value of ssl

#restart postgresql
sudo service postgresql restart
