#!/bin/sh

echo "Starting Server selinux"

#installing packages related to Selinux
sudo yum -y install policycoreutils policycoreutils-python selinux-policy selinux-policy-targeted libselinux-utils setroubleshoot-server setools setools-console mcstrans

#changing selinux.conf to change it to enforcing
sudo sed -i '/SELINUX/ s/'permissive'/'enforcing'/g' /etc/sysconfig/selinux #change value of SELINUX
