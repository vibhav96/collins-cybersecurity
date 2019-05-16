#!/bin/sh
echo "Starting Client Script"

set -e
set -x

#download postgresql-client
sudo yum -y install postgresql-server postgresql-contrib

#download ssh Server
yum install -y openssh-server

#install postgresql
sudo service postgresql initdb
sudo chkconfig postgresql on


#edit postgresql conf to allow outside connections
sudo sed -i 's/#listen_addresses/listen_addresses/g ' /var/lib/pgsql/data/postgresql.conf  #uncomment listen_addresses
sudo sed -i 's/#port/port/g ' /var/lib/pgsql/data/postgresql.conf  #uncomment listen_addresses
sudo sed -i '/listen_addresses/ s/'localhost'/'*'/g' /var/lib/pgsql/data/postgresql.conf #change value of listen_addresses


#start postgresql
sudo service postgresql start

echo "Client Script finished"
