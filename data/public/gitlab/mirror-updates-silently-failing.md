# Mirror Updates Silently Failing

## Symptoms

If logs suggest that a mirror was started but a success or failure log isn't present, it's possible that the job is silently failing.

## Synchronously Retry to Expose the Error

Retrying the mirror update synchronously in the Rails console might expose the error.

This first checks that an existing job is not running, and marks it as failed to safely execute the `UpdateMirrorService`.

```ruby

user = User.find(<user_id>) # user who created a pull mirror
project = Project.find(<project_id>) # project with a pull mirror configuration

# verify that the job is not running at the moment

completed_jids = Gitlab::SidekiqStatus.completed_jids([project.import_state.jid])

if completed_jids.present?
  puts 'The job is not running.'

  project.import_state.mark_as_failed('Manual failure through Rails console')

  result = Projects::UpdateMirrorService.new(project, user).execute

  puts result

  result
else
  puts 'The job is still running'
end

```
