## `hosted_runner_prepare` has failed with `Error: Error acquiring the state lock`

If you run `hosted_runner_deploy` on multiple runner stacks at the same time, and two `hosted_runner_prepare` jobs end up executing at once, then one or both will fail with `Error: Error acquiring the state lock`.

Just wait for `hosted_runner_prepare` to finish on all other stacks and then re-run `hosted_runner_deploy` on the stack which failed. This will re-run `hosted_runner_prepare` and also re-queue all the other jobs in the `hosted_runner_deploy` pipeline.
