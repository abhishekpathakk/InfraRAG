## pre bastion hosts

### How to start using them

SSH config is managed via [`glsh ssh-config`](ssh-config.md).

Once your config is in place, test it by ssh'ing to the deploy host:

```
ssh deploy-01-sv-pre.c.gitlab-pre.internal
```

### Console access

Currently we do not have a console host for preprod, to access the rails
console you can initiate it from one of the deploy host

```
ssh deploy-01-sv-pre.c.gitlab-pre.internal
sudo gitlab-rails console
```
