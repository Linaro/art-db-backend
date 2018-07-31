# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/trusty64"

  config.vm.network :forwarded_port, host: 8000, guest: 8000

  config.vm.provider "virtualbox" do |v|
    v.memory = 3024
    v.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
    v.customize ["modifyvm", :id, "--natdnsproxy1", "on"]
  end

  config.vm.provider :libvirt do |domain|
    domain.memory = 1024
  end

  if !ENV['NOPROVISION']
    config.vm.provision "shell" do |shell|
      shell.path = 'dev-setup.sh'
      shell.privileged = false
    end unless ENV['ANSIBLE']

    config.vm.provision "ansible" do |ansible|
      ansible.playbook = "ansible/site.yml"
    end if ENV['ANSIBLE']
  end

  config.ssh.forward_agent = true
end
