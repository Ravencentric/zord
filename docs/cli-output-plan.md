# Zord CLI output plan

**Status** · The visual direction is agreed and saved below. The next step is
to decide how output should behave in terminals and pipelines.

Zord should make it easy to see which task and command produced each part of a
terminal transcript. Zord’s own errors should be easy to find, and the layout
should stay compact when several commands run in succession.

## Agreed look

Use one heading per task, one `$` line per command, and a closing line from
Zord. Live output sits at the left margin. A blank line and the `zord error`
label distinguish a Zord diagnostic from command output. Use red for that
label when color is available.

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

zord error  test failed (pytest exited 1). 1 task skipped.
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

zord  1 task passed
```

### Quiet command failure

The command line shows the exit code. The Zord diagnostic below it gives
the reason if the failure stops the task.

```text
── release
$ git rev-parse --short HEAD  ✓ captured
$ git fetch origin           ✗ exit 128

zord error  release failed
  fatal: could not read from remote repository
```

## Working together

Start from the sketches above. Bring a concrete example to each open decision
and wait for agreement before editing the implementation. After that step, show
the resulting transcript and the checks that ran, then pause for review.
Update this file with the decision, the commit if there is one, and the next open
question. Advance one step at a time.

## Proposed order

1. **Choose where output goes.** Decide how Zord’s messages, child stdout, and
   child stderr should look in a terminal and behave in a pipeline.
2. **Try one task-level change.** Implement the task headings and end-of-run
   message. Review the output before moving on.
3. **Try one live command change.** Add command lines and check how they look
   with streaming output and an error. Include a command that ends mid-line.
4. **Try captured and quiet results separately.** Use the inline markers
   above. Decide which failure details to show and whether Zord should offer
   a quiet API before implementing that behavior.
5. **Carry the heading style through to listings and help.** Review each in
   the terminal and choose which details belong in the output.
6. **Choose the examples together.** Keep a small runnable corpus of the
   passing, failing, and mixed cases that helped make decisions.

## Resume from another machine

```console
git fetch origin
git switch --track origin/plan/cli-output
```

Read the status at the top of this file before starting another step.
