# Determine The GitLab Project Associated with a Domain

Incoming requests to GitLab Pages loadbalancers will include the requested domain in the logs. Mapping the domain to a project can be done on the Rails console with the following command.

```Ruby
domain=PagesDomain.find_by!(domain:"example.com")
```
