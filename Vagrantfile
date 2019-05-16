$ServerScript = <<-SERVERSCRIPT

#Downloading Dependencies
sudo yum -y install kernel-devel python-devel gcc-c++ cmake emacs numpy scipy build-essential
#sudo yum --enablerepo=extras install epel-release -y -- DON'T UNCOMMENT THIS LINE
sudo yum -y install python-pip
sudo yum -y install python-psycopg2

#Building Nitro
echo "Configuring NITRO"
set -e
set -x

#cd /vagrant/nitro-NITRO-2.7
cd /vagrant/nitro-NITRO-2.7/ && python waf configure --shared
cd /vagrant/nitro-NITRO-2.7/ && python waf clean
cd /vagrant/nitro-NITRO-2.7/ && python waf build
cd /vagrant/nitro-NITRO-2.7/ && python waf install

echo "cmake files"
#cd /vagrant/VT_NITFReader_library
cd /vagrant/VT_NITFReader_library && cmake .
cd /vagrant/VT_NITFReader_library && make

#running this python file will automatically extract metadata from .ntf files and populate the database
cd /vagrant/VT_NITFReader_library/ && python nitf_file_data_extraction.py

#sudo reboot
SERVERSCRIPT


Vagrant.configure("2") do |config|

  config.vm.define "server" do |server|

      server.vm.box = "bento/centos-6.7"
      server.vm.network "private_network" , type: "dhcp"
      #server.vm.network "public_network" , bridge: "en0: Wi-Fi (AirPort)"
      server.vm.provision "shell", inline: "sudo /bin/sh /vagrant/build/server_postgresql.sh"
      server.vm.provision "shell", inline: "sudo /bin/sh /vagrant/build/server_ssh.sh"
      server.vm.provision "shell", inline: "sudo /bin/sh /vagrant/build/server_selinux.sh"
      server.vm.provision "shell", inline: "sudo /bin/sh /vagrant/build/server_encryption.sh"
      server.vm.provision "shell", inline: $ServerScript
      server.vm.provision "shell", inline: "sudo /bin/sh /vagrant/build/server_firewall.sh"
      #server.vm.provision :reload


      server.vm.provider "virtualbox" do |vb|
            vb.name = "server"
        end

    end

 config.vm.define "client" do |client|

        client.vm.box = "bento/centos-6.7"
        client.vm.network "private_network" , type: "dhcp"
        #client.vm.network "public_network" , bridge: "en0: Wi-Fi (AirPort)"
        client.vm.provision "shell", inline: "sudo /bin/sh /vagrant/build/client.sh"

        client.vm.provider "virtualbox" do |vb|
            vb.name = "client"
        end

    end

end
