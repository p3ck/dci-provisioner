## Simple DCI provisioner

### Initial Setup

```
cd setup_virtual_lab
ansible-playbook -i inventory.yml setup_jumpbox.yml
```

### Running a job

```
cd setup_virtual_lab
ansible-playbook -i inventory.yml install_suts.yml
```
