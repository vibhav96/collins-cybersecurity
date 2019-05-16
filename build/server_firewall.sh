#!/bin/sh

echo "Starting Server Firewall"

#block all incoming and outgoing ports except ssh and postgresql
sudo chkconfig iptables on
sudo iptables -F #flush iptables
sudo iptables -A INPUT -i lo -j ACCEPT  #allowing loopback traffic to enter the server
sudo iptables -A OUTPUT -o lo -j ACCEPT  #allowing loopback traffic to leave the server
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT #allowing ssh traffic to enter the server
sudo iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT #allowing ssh traffic to leave the server
sudo iptables -A INPUT -p tcp --dport 5432 -j ACCEPT #allowing postgres traffic to enter the server
sudo iptables -A OUTPUT -p tcp --dport 5432 -j ACCEPT #allowing postgres traffic to leave the server
sudo iptables -P INPUT DROP #this drops all incoming packets that dont meet the iptables rules
sudo service iptables save #saving iptables rules
sudo service iptables restart #restarting iptables so all rules propagate

#sudo iptables -P INPUT ACCEPT #run this before doing iptables -F again
