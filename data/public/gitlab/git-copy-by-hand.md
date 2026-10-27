# Copying or moving a Git repository by hand

Most of the time, a Git repository on a Gitaly node can be copied from
a source location to the destination without any complication.

```bash
cp -a /path/to/source.git /path/to/destination.git
```

Or

```bash
cp -a /var/opt/gitlab/gitlab-data/repositories/@hashed/ab/cd/abcdblah.git \
  /var/opt/gitlab/gitlab-data/repositories/@hashed/wx/yz/wxyzblah.git
```

## Shared object pools

A space saving technique that Gitaly uses is to share objects between forked
Git repositories as a form of deduplication of disk blocks. When you move a
repository on a single Gitaly node, this is not an issue since the links to
these shared pools of objects are not broken/missing. But if you move a
repository from one Gitaly node to another, the shared pool will not exist on
the destination node. This can happen when restoring a repository from a
snapshot disk, or when moving a repository by hand to a new Gitaly node.

If, for example, you are copying a restored repository from a snapshot disk
into a new project repository, things may work fine until you unmount the
snapshot disk (which is removing the shared object storage location).

## Getting the shared objects moved

This example assumes you are restoring from a mounted drive, but these steps
can be adapted for remote copying.

1. Find the pool location by looking in the objects/info/alternates file. This is a sign that the repository is using shared pools.
2. Copy the remote pack files to the new project location.

   ```bash
   cp -r <pool location>/objects/pack <new git location>/project/pack
   ```

3. Remove the location from the alternates file.
4. Unpack everything in the new repository:

   ```bash
   find . -name '*.pack' -type f -exec sh -c 'cat {} | sudo -u git git unpack-objects' \;
   ```

5. Unmount the snapshot drive.
6. Run a git fsck to make sure it's all/mostly ok:

   ```bash
   sudo -u git git fsck
   ```

7. Delete the copied files by removing the pack directory and its contents in the new repository.
