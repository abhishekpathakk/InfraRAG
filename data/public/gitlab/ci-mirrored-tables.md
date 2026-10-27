# CI Mirrored Tables

The tables `gitlab_main` tables: `namespaces` and `projects` that reside on the `main` database, are partially
copied to their corresponding `gitlab_ci` database tables `ci_namespace_mirrors` and `ci_project_mirrors` respectively. This even happens on single database mode.

## Troubleshooting

When receiving alerts about inconsistent records errors, we need to
investigate the type of the inconsistency. This can be checked from
Kibana logs. For example, if it is inconsistent updating of the records,
or we have a delayed deletion of the records.

### Inconsistent Namespace Records

#### Links

- [Kibana Logs for Inconsistent Records](https://log.gprd.gitlab.net/app/discover#/view/b23c5a10-d3e3-11ed-a017-0d32180b1390?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:now-24h%2Fh,to:now))&_a=(columns:!(json.class),filters:!(('$state':(store:appState),meta:(alias:!n,disabled:!f,index:AWNABDRwNDuQHTm2tH6l,key:json.class,negate:!f,params:(query:CiNamespaceMirrorsConsistencyCheckWorker),type:phrase),query:(match_phrase:(json.class:CiNamespaceMirrorsConsistencyCheckWorker))),('$state':(store:appState),meta:(alias:!n,disabled:!f,field:json.extra.database_ci_namespace_mirrors_consistency_check_worker.results.mismatches,index:AWNABDRwNDuQHTm2tH6l,key:json.extra.database_ci_namespace_mirrors_consistency_check_worker.results.mismatches,negate:!f,params:(gte:1,lt:10000),type:range),query:(range:(json.extra.database_ci_namespace_mirrors_consistency_check_worker.results.mismatches:(gte:1,lt:10000))))),grid:(),hideChart:!f,index:AWNABDRwNDuQHTm2tH6l,interval:auto,query:(language:kuery,query:''),sort:!(!(json.time,desc))))

### Investigating the types of inconsistency

- Check the logs attribute `json.extra.database_ci_namespace_mirrors_consistency_check_worker.results.mismatches_details`

1. If the `mismatches_details` for the mismatched `namespaces` contains both `source_table` and `target_table`, then
this means that both source and target records exist in the source table and target table, but syncing is not working as expected. Check
the section [Wrong update of the mirrored records](#wrong-update-of-mirrored-records) in this page.

1. If the `mismatches_details` for the mismatched `namespaces` contains only the `source_table`, but not the `target_table`, then
this means that we are also not updating the records. Also check [Wrong update of the mirrored records](#wrong-update-of-mirrored-records) in this page.

1. If the `mismatches_details` for the mismatched `namespaces` contains only the `target_table`, but not the `source_table`, then
this means we are not deleting the target objects upon deletion of the source tables. Check [Delayed deletion of the mirrored records](#delayed-deletion-of-mirrored-records) in this page.

### Inconsistent Project Records

#### Links

- [Kibana Logs for Inconsistent Records](https://log.gprd.gitlab.net/app/discover#/view/b23c5a10-d3e3-11ed-a017-0d32180b1390?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:now-24h%2Fh,to:now))&_a=(columns:!(json.class),filters:!(('$state':(store:appState),meta:(alias:!n,disabled:!f,index:AWNABDRwNDuQHTm2tH6l,key:json.class,negate:!f,params:(query:CiProjectMirrorsConsistencyCheckWorker),type:phrase),query:(match_phrase:(json.class:CiProjectMirrorsConsistencyCheckWorker))),('$state':(store:appState),meta:(alias:!n,disabled:!f,field:json.extra.database_ci_project_mirrors_consistency_check_worker.results.mismatches,index:AWNABDRwNDuQHTm2tH6l,key:json.extra.database_ci_project_mirrors_consistency_check_worker.results.mismatches,negate:!f,params:(gte:1,lt:10000),type:range),query:(range:(json.extra.database_ci_project_mirrors_consistency_check_worker.results.mismatches:(gte:1,lt:10000))))),grid:(),hideChart:!f,index:AWNABDRwNDuQHTm2tH6l,interval:auto,query:(language:kuery,query:''),sort:!(!(json.time,desc))))

### Investigating the types of inconsistency

- Check the logs attribute `json.extra.database_ci_project_mirrors_consistency_check_worker.results.mismatches_details`

1. If the `mismatches_details` for the mismatched `projects` contains both `source_table` and `target_table`, then
this means that both source and target records exist in the source table and target table, but syncing is not working as expected. Check
the section [Wrong update of the mirrored records](#wrong-update-of-mirrored-records) in this page.

1. If the `mismatches_details` for the mismatched `projects` contains only the `source_table`, but not the `update_table`, then
this means that we are also not updating the records. Check
the section [Wrong update of the mirrored records](#wrong-update-of-mirrored-records) in this page.

1. If the `mismatches_details` for the mismatched `projects` contains only the `target_table`, but not the `source_table`, then
this means we are not deleting the target objects upon deletion of the source tables. Check [Delayed deletion of the mirrored records](#delayed-deletion-of-mirrored-records) in this page.

### Delayed deletion of mirrored records

- We use `LooseForeignKeys` to delete the mirrored tables. See the [Troubleshooting](https://docs.gitlab.com/development/database/loose_foreign_keys/#troubleshooting) section of this topic.

- Check the [logs of the job `LooseForeignKeys::CleanupWorker`](https://log.gprd.gitlab.net/app/discover#/?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:now-15m,to:now))&_a=(columns:!(),filters:!(('$state':(store:appState),meta:(alias:!n,disabled:!f,index:AWNABDRwNDuQHTm2tH6l,key:json.class,negate:!f,params:(query:'LooseForeignKeys::CleanupWorker'),type:phrase),query:(match_phrase:(json.class:'LooseForeignKeys::CleanupWorker')))),index:AWNABDRwNDuQHTm2tH6l,interval:auto,query:(language:kuery,query:''),sort:!(!(json.time,desc)))) in Kibana for any hints regarding troubleshooting the problem.

### Wrong update of mirrored records

- Check recent merged requests affecting these classes, and possibly revert them if necessary:

1. `app/models/namespaces/traversal/linear.rb`
1. `app/models/namespace/traversal_hierarchy.rb`
1. `app/models/namespace.rb`
1. `app/models/project.rb`
1. `app/models/namespaces/sync_event.rb`
1. `app/models/projects/sync_event.rb`

- If the problem happens on `namespaces`, then check the [logs of the jobs `Namespaces::ProcessSyncEventsWorker`](https://log.gprd.gitlab.net/app/discover#/view/b23c5a10-d3e3-11ed-a017-0d32180b1390?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:now-24h%2Fh,to:now))&_a=(columns:!(json.class),filters:!(('$state':(store:appState),meta:(alias:!n,disabled:!f,index:AWNABDRwNDuQHTm2tH6l,key:json.class,negate:!f,params:(query:'Namespaces::ProcessSyncEventsWorker'),type:phrase),query:(match_phrase:(json.class:'Namespaces::ProcessSyncEventsWorker')))),grid:(),hideChart:!f,index:AWNABDRwNDuQHTm2tH6l,interval:auto,query:(language:kuery,query:''),sort:!(!(json.time,desc)))).

- If the problem happens on `projects`, then check the logs of the jobs [`Projects::ProcessSyncEventsWorker`](https://log.gprd.gitlab.net/app/discover#/view/b23c5a10-d3e3-11ed-a017-0d32180b1390?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:now-24h%2Fh,to:now))&_a=(columns:!(json.class),filters:!(('$state':(store:appState),meta:(alias:!n,disabled:!f,index:AWNABDRwNDuQHTm2tH6l,key:json.class,negate:!f,params:(query:'Projects::ProcessSyncEventsWorker'),type:phrase),query:(match_phrase:(json.class:'Projects::ProcessSyncEventsWorker')))),grid:(),hideChart:!f,index:AWNABDRwNDuQHTm2tH6l,interval:auto,query:(language:kuery,query:''),sort:!(!(json.time,desc)))).

## Team

Reach out to the [Tenant Scale](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/tenant-scale/) in case of any extra help needed.

## References

- [CI Mirrored Tables](https://docs.gitlab.com/development/database/ci_mirrored_tables/)
- [Multiple Databases](https://docs.gitlab.com/development/database/multiple_databases/)
