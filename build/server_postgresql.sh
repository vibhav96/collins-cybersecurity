#!/bin/sh


echo "Starting Server postgresql"

#download postgresql
yum -y install postgresql-server postgresql-contrib

#install postgresql
sudo service postgresql initdb
sudo chkconfig postgresql on

#edit postgresql conf to allow outside connections
sudo sed -i 's/#listen_addresses/listen_addresses/g ' /var/lib/pgsql/data/postgresql.conf  #uncomment listen_addresses
sudo sed -i 's/#port/port/g ' /var/lib/pgsql/data/postgresql.conf  #uncomment listen_addresses
sudo sed -i '/listen_addresses/ s/'localhost'/'*'/g' /var/lib/pgsql/data/postgresql.conf #change value of listen_addresses

#start postgresql
service postgresql start

# postgres commands (\du and \dp)

echo "going to sleep for 10 seconds"
sleep 10

#creating group roles
sudo -u postgres psql -c "CREATE ROLE unclass;"
sudo -u postgres psql -c "CREATE ROLE secret;"
sudo -u postgres psql -c "CREATE ROLE topsecret;"


#creating user roles -- TO DO(CHANGE DEFAULT PASSWORDS)
sudo -u postgres psql -c "CREATE user system login password 'system';"
sudo -u postgres psql -c "CREATE user analystu login password 'analystu';"
sudo -u postgres psql -c "CREATE user analysts login password 'analysts';"
sudo -u postgres psql -c "CREATE user analystts login password 'analystts';"
sudo -u postgres psql -c "CREATE user fieldservice login password 'fieldservice';"
sudo -u postgres psql -c "CREATE user remotenodeu login password 'remotenodeu';"
sudo -u postgres psql -c "CREATE user remotenodes login password 'remotenodes';"
sudo -u postgres psql -c "CREATE user remotenodets login password 'remotenodets';"

#assigning user roles to groups
sudo -u postgres psql -c "GRANT unclass, secret, topsecret to system;"
sudo -u postgres psql -c "GRANT unclass to analystu;"
sudo -u postgres psql -c "GRANT unclass, secret to analysts;"
sudo -u postgres psql -c "GRANT unclass, secret, topsecret to analystts;"
sudo -u postgres psql -c "GRANT topsecret to fieldservice;"
sudo -u postgres psql -c "GRANT unclass to remotenodeu;"
sudo -u postgres psql -c "GRANT unclass, secret to remotenodes;"
sudo -u postgres psql -c "GRANT unclass, secret, topsecret to remotenodets;"



#creating tables
sudo -u postgres psql -f /vagrant/dbCreate.sql

#granting priveleges to groups
sudo -u postgres psql -c "GRANT select on unclass to unclass;"

sudo -u postgres psql -c "GRANT select on unclass to secret;"
sudo -u postgres psql -c "GRANT select on secret to secret;"

sudo -u postgres psql -c "GRANT select on unclass to topsecret;"
sudo -u postgres psql -c "GRANT select on secret to topsecret;"
sudo -u postgres psql -c "GRANT select on topsecret to topsecret;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES on unclass to fieldservice;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES on secret to fieldservice;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES on topsecret to fieldservice;"


#editing the file named "pg_hba.conf" in /var/lib/pgsql/data.

#adding entry host all all 0.0.0.0/0 md5 before the entry
#local all all       ident
sudo sed -i '/^local.*/i host   all    all    0.0.0.0/0    md5' /var/lib/pgsql/data/pg_hba.conf

#restart postgresql
sudo service postgresql restart
