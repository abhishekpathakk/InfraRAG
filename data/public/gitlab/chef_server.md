## Chef Server

We use Let's Encrypt SSL certificates for the CINC/Chef Server which are created and updated automatically using the [lego](https://github.com/go-acme/lego) utility. The utility is installed by the following recipe:

The `lego` utility and cronjob are deployed using the [gitlab-chef-server cookbokook](https://gitlab.com/gitlab-cookbooks/gitlab-chef-server/-/blob/master/recipes/default.rb)
