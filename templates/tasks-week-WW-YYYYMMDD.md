---
template: "20260808"
created: "{{date:YYYYMMDD}}"
tags:
  - created/{{date:YYYYMMDD}}
  - type/weekly-tasks
---
# Carryover
_Open tasks created before this week. Each one: work it, re-scope it, or drop it — carrying a task
untouched for a third week is a decision not to do it._
```tasks
path does not include 04-Archive
filter by function !task.isDone && task.created.moment?.isBefore(moment('{{date}}'), 'week')
sort by priority
```

# New this week

# Done this week
```tasks
filter by function (task.done.moment?.isSame(moment('{{date}}'), 'week') || task.cancelled.moment?.isSame(moment('{{date}}'), 'week') || false)
sort by priority
```

# Weekly review
_The retention mechanism for `00-Inbox`. See [[00-Inbox/README]]._

- [ ] Process the inbox — 2-minute rule on every capture; nothing stays as a to-do
- [ ] Any work-dir older than two weeks: promote to `02-Projects/` or archive
- [ ] Check each `active` project still is; move stalled ones to `blocked` or `paused`
- [ ] Nudge anything `blocked` — that status means someone *else* is the holdup

## Work-dirs due for a decision
```dataview
TABLE file.folder AS "Work dir", file.mtime AS "Last touched"
FROM "00-Inbox/work"
WHERE file.mtime <= date({{date}}) - dur(14 days)
SORT file.mtime ASC
```

## Projects by status
```dataview
TABLE status AS "Status", file.mtime AS "Last touched"
FROM "02-Projects"
WHERE status
SORT status ASC, file.mtime DESC
```
