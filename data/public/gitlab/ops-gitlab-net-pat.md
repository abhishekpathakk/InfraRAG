# OPS-GITLAB-NET Users and Access Tokens

The `ops-gitlab-net` user is our common account for automating interactions
with GitLab instances. Many CI jobs and automated tools use this user for
access to read and manipluate the Infrastructure GPRD and OPS data of GitLab
instances.

## Creating new tokens for use

### Name

The most important information about a token is where it is being employed.
You should not use an existing token for a new purpose. Create a new token
and name it clearly so that it can be found by others for rotation.

### Name Examples

A token used for repository synchronization might be named
`project FOO pull mirror`. This would indicate where the token is in use
so that rotating it is much easier.

A token used for API access might be named `project Bar@OPS CI var`.
This helps illustrate that the token is stored as a CI variable in the OPS
project `Bar`.

### Expiration

A default expiration of one year is ideal. If you need a token for testing,
consider a shorter term like three months.

[Setting an expiration will become a default in GitLab 16.](https://docs.gitlab.com/user/profile/personal_access_tokens/)

### Minimum Access Required

Only select the access required for all functionality the token will be
used for.

## Rotating old tokens

If the token is labeled well, finding and replacing the token with a new one
should be very straightforward.

1. Verify the token is in use where it says it is.
2. Note the name, access, and expiration of the existing token and revoke it.
3. Create a new token with appropriate name, access, and expiration date.
4. Update the token wherever it is being used.

If the token is not clearly labeled, these additional steps may help uncover
where the token is in use.

### Project Searches

If the token has a name that is non-generic, it may be a reference to a
project. Using the GitLab search could help find a project like this.

### Kibana Searches

The rails logs probably won't help you determine who is making the API calls
to use the token, but seeing what actions are being taken could be a clue.
The `json.token_id` and `json.token_type` can help you narrow down requests
from a specific token ID.

[Example Kibana Search](https://log.gprd.gitlab.net/goto/19e296e0-3851-11ed-b86b-d963a1a6788e)

### 1Password Searches

Searching in 1password could also reveal the intention of the token.
