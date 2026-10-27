# Recovering a repository with a broken object pool relationship (alternates file)

This runbook covers recovering a repository that is corrupt because its
`objects/info/alternates` file points to a non-existent object pool repository.
A single such repository can drive enough `Internal` gRPC errors to violate the
error-rate SLO for a whole node.

Note that recovery in most cases is not possible. This serves mainly as a
troubleshooting guide.

This is a different failure mode from ref corruption, which can occur if the
host is shut down uncleanly. If you are dealing with corrupted refs rather than
a missing pool, see
[gitaly-repository-corruption.md](gitaly-repository-corruption.md) instead.

## Symptoms

- Gitaly logs contain the string `unable to normalize alternate object path`,
  and
- The goserver error rate SLO is violated, or
- The errors are gRPC `Internal` errors.

## Procedure

A repository is using a pool when it has an `objects/info/alternates` file. The
line in that file is a relative path to a pool's `objects` directory. The
alternate is broken when that target directory no longer exists.

### 1. Check a repository for broken alternates

1. SSH onto the Gitaly node hosting the affected repository and check the
   alternates file of the affected repository. Repositories are stored as a
   `@hashed` path beginning at `/var/opt/gitlab/git-data/repositories`, which is
   the repository storage root. You can find the `@hashed` path in two ways:
   - If you have administrator access to the GitLab instance, the `@hashed` path
     will be listed in the project settings in the admin area.
   - Gitaly logs emit the `@hashed` path in the `grpc.request.repoPath` field.
     The corresponding `grpc.request.glProjectPath` field in the log will
     represent the project.

```bash
cd /var/opt/gitlab/git-data/repositories/@hashed/ab/cd/abcd...ef.git
cat objects/info/alternates
```

If directory defined in `objects/info/alternates` is missing, the pool is gone
and the alternate is broken. If the directory exists, another problem may be
occurring.

It is possible for the pool repository to exist on a different Gitaly node. This
can happen as an edge case of an operation like a repository move. If the
affected repository has been moved from a different Gitaly node in the past,
check the previous Gitaly node to see if the pool repository exists there. The
pool paths are globally unique, so a matching path on another node is guaranteed
to be the same pool.

There are no automated ways to determine if the pool exists on a different node.
One possible approach is to write a script that executes `find(1)` on each node.
Pool repositories are stored in a fixed path under
`/var/opt/gitlab/git-data/repositories/@pools`.

### 2. Back up the repository

`cd` into the hashed repository directory and snapshot it. It's recommended to
output the snapshot under `/var/opt/gitlab`, as this is the mountpoint of the
largest storage disk on the VM.

Before proceeding, you should ensure there is adequate free space in the
destination.

```bash
# Check the size of the repository
du -sh /var/opt/gitlab/git-data/repositories/@hashed/ab/cd/abcd...ef.git

# Check the amount of free space in the destination.
df -h /var/opt/gitlab

cd /var/opt/gitlab/git-data/repositories/@hashed/ab/cd/abcd...ef.git
# It may be useful to name the file after the incident/issue ID.
tar cvf /var/opt/gitlab/<issue_id>.tar .
```

### 3a. Delete the alternates file

Perform this step only if the pool is missing from every Gitaly node.

With the pool confirmed missing, the alternates file becomes useless. Remove the
file:

```bash
rm objects/info/alternates
```

### 3b. Repair the alternates file

Perform this step only if the pool exists in another Gitaly node.

Copy the pool directory from the other Gitaly node into the same location on
this Gitaly node. Follow [git-copy-by-hand.md](git-copy-by-hand.md) to do this.

### 4. Run `git fsck` to assess the damage

```bash
git fsck
```

Interpret the result:

- If no errors are returned and:
  - Step 3a was performed - objects in the missing pool were not actively being
    referenced. The repository should now be in a healthy state.
  - Step 3b was performed - the objects in the pool copied from the other Gitaly
    node were sufficient. The repository should now be in a healthy state.
- If errors are returned, the missing objects cannot be recovered. It may be
  necessary to accept data loss and inform the owners of the affected
  repository.

### 5. Delete the backup

Once the repository is either fixed, or deemed unrepairable, it is time to remove
the `.tar` created in Step 2.

```bash
rm /var/opt/gitlab/<issue_id>.tar .
```

## Related runbooks

- [gitaly-repository-corruption.md](gitaly-repository-corruption.md) -
  recovering corrupted refs after an unclean shutdown.
- [find-project-from-hashed-storage.md](find-project-from-hashed-storage.md) -
  mapping between hashed paths and projects.
- [git-copy-by-hand.md](git-copy-by-hand.md) - moving repositories and their
  shared object pools by hand.
- [access-repository-through-teleport.md](access-repository-through-teleport.md)
  - getting shell access to a Gitaly node.
