# ShellTools File-Operation Path Containment

## Security issue

`ShellTools.read()`, both forms of `replace()`, and `write_file()` resolved
user-controlled paths but did not verify that the result remained beneath
`ShellTools.cwd`. Absolute paths and `..` components could therefore read or
modify files elsewhere on the host. Match harvesting used the same unsafe
resolution when creating editable file matches.

## Patch

All non-shell filesystem access now goes through a shared `_resolve_path()`
helper. It resolves both the working directory and candidate path, then requires
`resolved.relative_to(cwd)` to succeed before any file is opened, created, or
modified. A path outside the current working directory raises `ValueError`.

Normal relative paths, nested directories, overwrites, and both existing
`replace()` forms retain their behavior. Match harvesting fails closed and
attaches no editable matches when a reported path is outside the working
directory.

## Boundary

This change confines the explicit Python file-operation methods. `run()` is an
intentional shell capability and must be separately sandboxed or withheld when
arbitrary shell commands are outside the deployment's trust model.
