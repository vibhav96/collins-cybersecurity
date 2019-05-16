#!/bin/sh

echo "Starting Server ssh"

#download ssh Server
yum install -y openssh-server

#enable ssh to start automatically at boot time
sudo chkconfig sshd --add


sudo useradd fieldservice #adding user
sudo echo "fieldservice:fieldservicepassword" | chpasswd #changing password

#giving fieldservice root priveleges
sudo touch fieldservice
sudo bash -c "echo '%fieldservice ALL=(ALL) PASSWD: ALL' >> fieldservice"
sudo mv fieldservice /etc/sudoers.d
