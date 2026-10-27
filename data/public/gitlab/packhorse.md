Packhorse is a caching layer for git fetches that sits closer to the CI
runners, it is meant to help reducing the load on Gitaly by coalescing fetches
that target the same SHA, caching the relevant git objects for similar upcoming
requests.

During the initial pilot, CI runners send a request to HAProxy CI, which is
forwarded to Packhorse if the URL matches one of the URLs configured in
HAProxy. Packhorse itself is configured with an allow list, which decides whether
to act on the request or let it pass through.

The HAProxy filter may seem redundant, but it is necessary to avoid sending the
entirety of CI traffic (or even a percentage of it) through Packhorse before
verifying it can actually handle the load.

Packhorse metrics are accessible from this
[dashboard](https://dashboards.gitlab.net/d/packhorse-main/packhorse3a-overview?orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-packhorse-main-gprd&var-stage=main).

To check whether caching would help a repo before adding it to the allow list,
see [Evaluate a hot repository for Packhorse caching](evaluate-repo.md).

## Troubleshooting

### CI jobs are failing for a repo cached by Packhorse

Check the logs in Kibana for hints regarding the failure. If nothing is obvious
and restoring normal operations is paramount, remove (or comment out) the repo
from Packhorse allow list, as defined in
[ArgoCD](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/beecc92a0deb9226e9d32f85fe190bf9dc20fcac/services/packhorse/env/gprd/clusters/packhorse-main-gprd/values.yaml#L21).

This will cause all requests to the affected repo to pass through Packhorse
with no caching or coalescing. If this didn't resolve the issue, then consider
removing the URL of the repo from [HAProxy
CI](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/d515ee163889551ead961b794fc74924fe883098/roles/gprd-base-haproxy-ci.json#L24)
Chef configuration to bypass Packhorse altogether.


### Packhorse on-disk cache size is saturated

Each Packhorse pod has a local disk attached that is used to cache git
packfiles. In any case, it may prove useful to get a listing of all the cached
packfiles on the affected pod for an inspection later, so better do that before
applying a remedy.

You need to have access to production's console node to be able to connect to
the pod. Afterwards, execute these commands:

```bash
glsh kube setup # One-time setup to configure the cluster credentials
glsh kube use-cluster packhorse-main-gprd
kubectl exec -t -n packhorse <affected-pod-name> -- ls -Shal /tmp/packhorse-cache | tee cached-packfiles
```

#### Remedies

It may be that the cache maximum age is too high and a particular pod is
accumulating too much for too long. In that case, consider lowering the
[`maxIdleAge`
value](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/beecc92a0deb9226e9d32f85fe190bf9dc20fcac/services/packhorse/env/gprd/clusters/packhorse-main-gprd/values.yaml#L16)
to something reasonable.

If this does not solve it, there could be a bug in Packhorse that prevents it
from properly evicting cached items, so to relieve the pod consider removing
cached files manually from the pod.
