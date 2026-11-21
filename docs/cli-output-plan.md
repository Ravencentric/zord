# Zord CLI output plan

**Status** · Live command lines and captured command statuses are ready for
review. Run the demo tasks below to see the current design. The next open
decision is how to handle quiet commands.

Zord should make it easy to see which task and command produced each part of a
terminal transcript. Zord’s own errors should be easy to find, and the layout
should stay compact when several commands run in succession.

## Agreed look

Use one heading per task and one `$` line per command. Live output sits at the
left margin. A run error gets its own `── zord` section after a blank line.
The first line below the heading starts with `error:` in red when color is
available. A successful run ends with the last task's output.

### Live commands and a failing batch

```text
── check

$ uv run ruff check
All checks passed!

$ uv run ruff format --check
12 files already formatted

── test

$ uv run pytest -q
1 failed, 27 passed

── zord
error: test failed (pytest exited 1)
skipped: later
```

### Captured and quiet commands on success

Put the result on the command line itself. The `captured` label identifies
output returned to the task.

```text
── release
$ git rev-parse --short HEAD  ✓ captured
$ git fetch origin           ✓

$ uv build
Successfully built zord-0.1.0
```

### Quiet command failure

The command line shows the exit code. The Zord diagnostic below it gives
the reason if the failure stops the task.

```text
── release
$ git rev-parse --short HEAD  ✓ captured
$ git fetch origin           ✗ exit 128

── zord
error: release failed
  fatal: could not read from remote repository
```

## Agreed run-output routing

Send Zord's task headings, command lines, and diagnostics to stderr.
Live child stdout stays on stdout, and live child stderr stays on stderr.
This keeps command output usable in pipelines and redirected files.

For example, suppose a `version` task runs `python -c "print('0.1.0')"`:

```console
zord version > version.txt
```

The terminal shows Zord's messages:

```text
── version

$ python -c "print('0.1.0')"
```

The file `version.txt` contains only:

```text
0.1.0
```

## Task-level implementation

Committed as `002ac24`.

Selected tasks, default tasks, and single-task invocations with `--` share the
same output format. Each task gets a heading. A failure stops the batch and
lists any unstarted tasks by name in run order on a `skipped:` line below the
`error:` message. Cause details follow. An interruption also uses the
`── zord` heading.

Task stdout is flushed before moving to the next heading or showing an error.
Live child stdout and stderr keep their respective streams.
For a captured command failure, the CLI shows the exception chain. The task
can read captured stderr from the exception.

These examples show the task output with color disabled.

### Passing task (exit 0)

```text
── check
All checks passed!
```

### Failing batch (exit 1)

```text
── check
All checks passed!

── test
1 failed, 27 passed

── zord
error: test failed
skipped: later

caused by:
    0: RuntimeError: tests failed
       in test() at tasks.py:12:5
```

Checks run:

- `uv run --locked pytest -q`: 260 passed.
- `uv run --locked ruff check`: passed.
- `uv run --locked ruff format --check`: passed.
- `uv run --locked pyrefly check`: 0 errors.
- CLI tests cover successful runs without a footer, failed and interrupted
  runs with a `── zord` section, and separate live child streams.

## Live command lines — ready for review

`Cmd.run()` prints a `$` line to stderr before launching a child. Each `$` line
starts with a newline, including the first command under a task heading. This
ends any partial line from the previous command, or adds a blank line after a
complete line.
The line shows the resolved executable's filename. On Windows it omits common
executable extensions such as `.exe`, `.cmd`, and `.bat`.
The preview shows the first line of a multiline argument followed by `...`.
The child receives the full argument.
Child streams stay inherited, so redirection preserves child stdout exactly.

The passing preview included both kinds of spacing.

```text
── check

$ python emit.py ready
Ready

$ python emit.py working
working...
$ python emit.py done
Done
```

The failing batch continued from `check` into `test`.

```text
── test

$ python emit.py fail
A check failed

── zord
error: test failed
skipped: later
```

The `caused by:` block followed with `CalledProcessError` and exit status 1.
With stdout redirected, `check` produced `Ready\nworking...Done\n` on stdout.

All 260 tests passed, along with Ruff lint and formatting and Pyrefly. The
CLI previews verified successful and failing exit codes, combined output,
and separate stdout and stderr.

## Captured command statuses — ready for review

`Cmd.capture()` and `Cmd.stdout()` print the `$` command to stderr before
launching it. When it exits, they append `✓ captured` or `✗ exit N` to the same
line, including when `.check(False)` lets the task continue. If no exit code
is available, the line ends before the error diagnostic. Captured output stays
available to the task.

```text
── verify

$ python -c print(42)  ✓ captured

── fail

$ python -c "raise SystemExit(7)"  ✗ exit 7

── zord
error: fail failed
```

The `caused by:` block followed with `CalledProcessError`. All 260 tests and
the Ruff and Pyrefly checks passed. The next open question is whether to add a
quiet command API and what its failures should show.

## Runnable examples

Run the [demo tasks](../examples/cli-output/tasks.py) from their directory.

```console
cd examples/cli-output
uv run --locked --project ../.. zord --default
uv run --locked --project ../.. zord live fail-live captured
uv run --locked --project ../.. zord live fail-captured captured
```

The default run shows live output, a truncated argument preview, a line that
ends mid-line, and a successful capture. Both failure runs skip `captured`.
The live failure shows the child's stderr, and the captured failure shows
`✗ exit 7` on the command line.

## Working together

Start from the sketches above. Bring a concrete example to each open decision
and wait for agreement before editing the implementation. After that step, show
the resulting transcript and the checks that ran, then pause for review.
Update this file with the decision, the commit if there is one, and the next open
question. Advance one step at a time.

## Proposed order

1. **Choose where output goes — agreed.** Zord's run messages go to stderr;
   live child stdout and stderr keep their respective streams, as described above.
2. **Try one task-level change — implemented.** Task headings and the error
   section use the agreed stderr routing.
3. **Try one live command change — ready for review.** The examples above show
   streaming output, a failure, and a command that ends mid-line.
4. **Try captured and quiet results separately.** Captured statuses are ready
   for review. Decide whether Zord should offer a quiet API and which failure
   details it should show before implementing it.
5. **Carry the heading style through to listings and help.** Review each in
   the terminal and choose which details belong in the output.
6. **Choose the examples together.** The demo tasks cover the current passing,
   failing, and mixed cases. Revisit them as the remaining output decisions land.

## Resume from another machine

```console
git fetch origin
git switch --track origin/plan/cli-output
```

Read the status at the top of this file before starting another step.
