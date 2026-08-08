---
template: "20260808"
created: "{{date:YYYYMMDD}}"
tags:
  - created/{{date:YYYYMMDD}}
  - daily-note
---
# Meetings
_What's on the calendar today?_

| Time | Meeting Title | Length | Follow-up |
| ---- | ------------- | ------ | --------- |
|      |               |        |           |

### recent meetings
_Context from recent discussions_
```dataview
TABLE file.name AS "Meeting", file.mtime AS "Date"
FROM "Log/meetings"
WHERE file.mtime >= date({{date}}) - dur(7 days) AND file.mtime <= date({{date}})
SORT file.mtime DESC
LIMIT 5
```

# Today's Plan
_Brief summary of your intentions. A high-level description of what is to be accomplished today._

→ This week's priorities: `Log/<week-Monday>/priorities-week-of-<week-Monday>.md`

## Inbox Review
_Items needing processing from daily capture. The 2-minute rule: do it now, or route it to
Projects / Resources / Archive. Nothing lives in the inbox as a to-do._
```dataview
TABLE file.name AS "File Name", file.mtime AS "Modified"
FROM "00-Inbox"
WHERE file.mtime >= date({{date}}) - dur(3 days) AND file.mtime <= date({{date}})
SORT file.mtime DESC
LIMIT 10
```

### work-dirs older than two weeks
_Graduate to `02-Projects/` or archive — none linger. See [[00-Inbox/README]]._
```dataview
TABLE file.folder AS "Work dir", file.mtime AS "Last touched"
FROM "00-Inbox/work"
WHERE file.mtime <= date({{date}}) - dur(14 days)
SORT file.mtime ASC
LIMIT 10
```

# TODO
_Open tasks, excluding the archive_
```tasks
path does not include 04-Archive
filter by function !task.isDone && task.created.moment?.isSameOrBefore(moment('{{date}}'), 'day') || false
sort by priority
```

# DONE
_Accomplishments today_
## planned
```tasks
filter by function task.done.moment?.isSame(moment('{{date}}'), 'day') || false
sort by priority
```

## work context
### active projects
_Committed work with a finish line_
```dataview
TABLE file.name AS "Project", status AS "Status", file.mtime AS "Last Modified"
FROM "02-Projects"
WHERE file.mtime >= date(today) - dur(14 days)
SORT file.mtime DESC
LIMIT 8
```

### areas touched recently
_Ongoing responsibilities — no finish line_
```dataview
TABLE file.name AS "Area note", file.mtime AS "Modified"
FROM "01-Areas"
WHERE file.mtime >= date(today) - dur(7 days)
SORT file.mtime DESC
LIMIT 5
```

## unplanned
_Fly-ins?_

## other
_files created today_
```dataview
TABLE file.name AS "File Name", file.folder AS "Folder"
WHERE (contains(file.name, "{{date:YYYYMMDD}}") OR contains(file.tags, "created/{{date:YYYYMMDD}}")) AND file.name != this.file.name
SORT file.folder ASC
```
_files updated today_
```dataview
TABLE file.name AS "File Name", file.folder AS "Folder"
WHERE contains(file.tags, "updated/{{date:YYYYMMDD}}") AND file.name != this.file.name
SORT file.folder ASC
```

## reference added or changed
_New or updated how-tos, runbooks, distilled knowledge_
```dataview
TABLE file.name AS "Resource", file.mtime AS "Modified"
FROM "03-Resources"
WHERE file.mtime >= date(today) - dur(7 days)
SORT file.mtime DESC
LIMIT 5
```

# WONT DO
```tasks
filter by function task.cancelled.moment?.isSame(moment('{{date}}'), 'day') || false
sort by priority
```

---

<!-- Embed anything you want in front of you every day — e.g. a standing priorities note.
     Uncomment and point it at a note you've created:
       `![[01-Areas/<Area-Name>/top-of-mind#Big Bets]]`
     Create the note first: an embed pointing at a missing file renders as plain text. -->
