# YAML Spec Cache

last_fetched: 2026-11-02T04:20:46Z
fetcher: scripts/build-yaml-spec-cache.py

## Source (skills): https://docs.claude.com/en/docs/claude-code/skills

Extend Claude with skills - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
Skills extend what Claude can do. Create a
SKILL.md
file with instructions, and Claude adds it to its toolkit. Claude uses skills when relevant, or you can invoke one directly with
/skill-name
.
Create a skill when you keep pasting the same instructions, checklist, or multi-step procedure into chat, or when a section of CLAUDE.md has grown into a procedure rather than a fact. Unlike CLAUDE.md content, a skill’s body loads only when it’s used, so long reference material costs almost nothing until you need it.
For built-in commands like
/help
and
/compact
, and bundled skills like
/debug
and
/code-review
, see the
commands reference
.
Custom commands have been merged into skills.
A file at
.claude/commands/deploy.md
and a skill at
.claude/skills/deploy/SKILL.md
both create
/deploy
and work the same way. Your existing
.claude/commands/
files keep working. Skills add optional features: a directory for supporting files, frontmatter to
control whether you or Claude invokes them
, and the ability for Claude to load them automatically when relevant.
Claude Code skills follow the
Agent Skills
open standard, which works across multiple AI tools. Claude Code extends the standard with additional features like
invocation control
,
subagent execution
, and
dynamic context injection
. See
Using skill frontmatter outside Claude Code
for which frontmatter fields are part of the standard and which are Claude Code extensions.
​
Bundled skills
Claude Code includes a set of bundled skills, such as
/doctor
,
/code-review
,
/batch
,
/debug
,
/loop
, and
/claude-api
. Bundled skills are prompt-based: they give Claude detailed instructions and let it orchestrate the work using its tools. Most built-in commands instead execute fixed logic directly.
You invoke a bundled skill the same way as any other skill, by typing
/
followed by the skill name. Claude invokes some bundled skills automatically when relevant; others, including
/verify
, run only when you invoke them, which keeps you in control of when these longer-running checks spend time and tokens.
Most bundled skills are available in every session. A few depend on a specific feature:
/workflow-authoring
, for example, is available only when
dynamic workflows
are enabled.
To turn bundled skills off, use the
disableBundledSkills
setting.
The
/doctor
setup checkup stays typable when
disableBundledSkills
is on. To hide it, set the
DISABLE_DOCTOR_COMMAND
environment variable or a
skillOverrides
entry of
"doctor": "off"
.
Bundled skills are listed alongside built-in commands in the
commands reference
, marked
Skill
in the Purpose column.
​
Check your setup with
/doctor
Run
/doctor
at the Claude Code prompt for a setup checkup that diagnoses issues and can fix them. Claude reports its findings first and asks for confirmation before changing anything. The checkup covers these areas:
Installation health
: duplicate or leftover installs,
PATH
problems, unparseable settings files, and whether a newer version is available on your
release channel
Extensions
: unused skills, MCP servers, and plugins compared with their context cost, and slow
hooks
CLAUDE.md
files
: local
CLAUDE.md
files that duplicate checked-in ones, checked-in
CLAUDE.md
content Claude could derive from the codebase
, and the always-loaded guidance that remains, which Claude offers to migrate into skills and nested
CLAUDE.md
files that load on demand
Permissions
: an offer to make
auto mode
your default permission mode and to
pre-approve
read-only commands that you frequently deny
Usage
: on a Pro, Max, Ultra, Team, or Enterprise plan, the
changes
/usage
recommends
to lower your plan usage, measured over the last 7 days. Claude proposes the changes it can make itself and reports the rest as advice, such as a command for you to run. The usage check requires Claude Code v2.1.305 or later, and
/doctor
leaves it out while
Remote Control
is connected.
For read-only installation diagnostics without starting a session, run
claude doctor
in your terminal instead.
To audit your instructions rather than your setup, run
/doctor prompt-audit
at the Claude Code prompt. Claude
checks your
CLAUDE.md
files, skills, and other configuration
for outdated or conflicting instructions instead of running the checkup. The
prompt-audit
subcommand requires Claude Code v2.1.283 or later.
​
Run and verify your app
Three bundled skills work together to launch your app and confirm changes against the running app instead of tests alone:
Skill
Purpose
/run
Launch and drive your app to see a change working
/verify
Build and run your app to confirm a code change does what it should, without falling back to tests or type checks
/run-skill-generator
Teach
/run
and
/verify
how to build and launch your project
/run
and
/verify
work without setup. They infer the launch from your project type (CLI, server, TUI, browser-driven) and from what’s in your README,
package.json
, or
Makefile
. That inference gets unreliable for projects that need anything beyond a standard launch: a database, an env file, a graphical session, a multi-step build.
/run-skill-generator
records the recipe instead. It gets your app running from a clean environment, captures what worked (the install commands, the env vars, the launch script), and commits it as a per-project skill at
.claude/skills/run-<name>/
. After that,
/run
,
/verify
, and any other agent in the repo follow the recorded recipe instead of rediscovering it. Run
/run-skill-generator
once per project, and again if the build or launch process changes.
/verify
can also record its own recipe. When it has to build and drive your app without a recorded recipe, it writes what worked to
.claude/skills/verify/SKILL.md
at the repo root, or in the touched package directory in a monorepo, so later runs and other agents follow the same steps. At the repo root, the recorded skill replaces the bundled
/verify
.
Claude edits the recorded file only when it steered a run wrong, such as a command that failed or a missing step, so you can commit the file without per-session diffs.
​
Run your checks before each commit
When a session starts with a skill named
verify
or
simplify
in place, Claude Code’s commit instructions tell Claude to run it right before each commit, except for changes to docs or tests. This requires Claude Code v2.1.286 or later. Claude gets that instruction when these conditions hold at the start of the session:
Location
: the skill loads from the enterprise, personal, project, or additional-directory
location
, or from a
.claude/commands/
file with that name. The recipe that
/verify
records at your repo root is a project skill, so it counts. The bundled
/verify
and
/simplify
, plugin skills, and skills from your claude.ai account don’t count.
Invocation
: Claude can invoke the skill. If you’ve
stopped Claude from invoking it
, for example with
disable-model-invocation: true
, Claude doesn’t get the instruction.
Git instructions
: you haven’t turned off
includeGitInstructions
. Turning it off removes this instruction together with the rest of the built-in commit and PR instructions.
​
Work on Claude API projects
The bundled
/claude-api
skill loads
Claude API
and
Managed Agents
reference material for your project’s language. Claude also activates it automatically when your code imports
anthropic
or
@anthropic-ai/sdk
.
To start one of the skill’s workflows, type a subcommand after the skill name at the Claude Code prompt, for example
/claude-api migrate
. The table lists what each subcommand does and the earliest Claude Code version that includes it.
migrate
and
managed-agents-onboard
predate v2.1.221, the oldest version the table tracks.
Subcommand
What it does
Minimum version
migrate
Update your existing Claude API code to a newer model
Earlier than v2.1.221
upgrade
Upgrade your project’s Anthropic SDK to a new major version and update your code for its breaking changes
v2.1.236 or later
api-version
Update your Claude API code for a newer
API version
, then switch your requests to that version
v2.1.307 or later
managed-agents-onboard
Walk through creating a new Managed Agent
Earlier than v2.1.221
managed-agents-onboard <url>
Build the Managed Agent that the page at the URL describes, such as a page in the
Managed Agents docs
v2.1.290 or later
managed-agents-onboard <quickstart-name>
Build one of the Console’s quickstart templates, such as
deep-researcher
. If you give one word that isn’t a template name, Claude lists the valid names
v2.1.290 or later
managed-agents-secure [<agent-id>]
Read the settings of one Managed Agent and report where they match the
Secure your Managed Agents deployment
guide or differ from it. Requires the
ant
CLI
v2.1.304 or later
prompt-audit
Flag instructions written for older models in your prompts, skills, and tool descriptions and propose fixes as a diff
v2.1.221 or later
cost-optimize
Profile where your project’s Claude API spend goes and propose savings from options such as prompt caching, trimming unneeded input and output tokens, batch processing, effort, and model choice, one change at a time
v2.1.247 or later
build-eval
Build an eval set for your Claude-powered app
v2.1.259 or later
hillclimb
Iteratively improve your app against an existing eval
v2.1.259 or later
preserved-thinking-migration
Find the edits your integration makes to earlier turns, its system prompt, or its tool list that invalidate
preserved thinking
blocks, measure how much reasoning each one drops, and propose fixes one at a time, re-measuring after each change
v2.1.282 or later
​
Getting started
​
Create your first skill
This example creates a skill that summarizes the uncommitted changes in your git repository and flags anything risky. It pulls the live diff into the prompt before Claude reads it, so the response is grounded in your actual working tree rather than what Claude can guess from open files. Claude loads the skill automatically when you ask about your changes, or you can invoke it directly with
/summarize-changes
.
1
Create the skill directory
Create a directory for the skill in your personal skills folder. Personal skills are available across all your projects.
mkdir
-p
~/.claude/skills/summarize-changes
2
Write SKILL.md
Every skill needs a
SKILL.md
file with two parts: YAML frontmatter between
---
markers that tells Claude when to use the skill, and markdown content with the instructions Claude follows when the skill runs. The directory name, or the frontmatter
name
when you set one, becomes the command you type, and the
description
helps Claude decide when to load the skill automatically.
Save this to
~/.claude/skills/summarize-changes/SKILL.md
:
---
description
:
Summarizes uncommitted changes and flags anything risky. Use when the user asks what changed, wants a commit message, or asks to review their diff.
---
## Current changes
!`git
diff HEAD`
## Instructions
Summarize the changes above in two or three bullet points, then list any risks you notice such as missing error handling, hardcoded values, or tests that need updating. If the diff is empty, say there are no uncommitted changes.
The
!`git diff HEAD`
line uses
dynamic context injection
: Claude Code runs the command and replaces the line with its output before Claude sees the skill content, so the instructions arrive with the current diff already inlined.
3
Test the skill
Open a git project, make a small edit to any file, and start Claude Code by running
claude
. You can test the skill two ways.
Let Claude invoke it automatically
by asking something that matches the description:
What did I change?
Or invoke it directly
with the skill name:
/summarize-changes
Either way, Claude should respond with a short summary of your edit and a list of risks.
​
Choose where skills load
Where you save a skill decides which sessions load it. Save it under your home directory to get it in every project, commit it to a repository to share it with everyone who works there, or distribute it through a plugin or managed settings to reach a whole team.
Location
Path
Loads in
Enterprise
.claude/skills/<skill-name>/SKILL.md
in the
managed settings directory
All users on machines where your organization deploys it
Personal
~/.claude/skills/<skill-name>/SKILL.md
All your projects on this machine, but not
Cowork or cloud sessions
Project
.claude/skills/<skill-name>/SKILL.md
Sessions in this repository, but not
cloud threads in a project
. Commit it so your team gets it too
Nested
<subdir>/.claude/skills/<skill-name>/SKILL.md
Sessions started in or below
<subdir>
, but not cloud threads in a project. Outside those threads, a session started above it loads the skill once Claude works on files there. See
monorepos and subdirectories
Additional directory
.claude/skills/<skill-name>/SKILL.md
in a directory you pass with
--add-dir
That session. See
directories outside the project
Plugin
<plugin>/skills/<skill-name>/SKILL.md
Wherever the
plugin
is enabled, as
/plugin-name:skill-name
claude.ai account
Skills enabled for your claude.ai account
Cowork sessions, cloud sessions, and terminal sessions where you sign in with that account. See
Skills synced from claude.ai
Skill folders also follow these rules:
Symlinked folders
: a
<skill-name>
entry in the enterprise, personal, or project location can be a symlink to a directory elsewhere on disk. Claude Code reads
SKILL.md
from the target and loads the skill once even if several locations point at the same target. Plugin skills
handle symlinks differently
.
Reserved name
synced
: don’t name a skill folder
synced
, in any capitalization. Claude Code uses
~/.claude/skills/synced/
for
skills downloaded from claude.ai
and skips a skill you author at that name in the enterprise, personal, and project locations.
Reserved name
anthropic-skills
: outside a plugin, a skill folder or command file whose name is
anthropic-skills
or starts with
anthropic-skills:
doesn’t load. See
Names reserved for synced skills
.
Characters in the name
: outside a plugin, a skill folder doesn’t load when its name has a character such as a zero-width space or
<
. See
Characters a skill name can’t hold
.
Command files
: a Markdown file in
.claude/commands/
is the older format and still works. It supports the same
frontmatter
except
name
and
paths
. To find the name you type to invoke it, see
How a skill gets its command name
. Prefer a skill for new work, since skills also support
supporting files
.
Skill folder as a plugin
: add a
.claude-plugin/plugin.json
to a personal or project skill folder and Claude Code can load it as a
plugin
named
<name>@skills-dir
with its own agents, hooks, and MCP servers. In a project’s
.claude/skills/
, this requires accepting the workspace trust dialog first, and in either location it requires that your administrator hasn’t
blocked skills-directory plugins
.
​
Load skills in monorepos and subdirectories
Claude Code loads project skills from
.claude/skills/
in the directory where you start it and in every parent directory up to the repository root, so starting in
packages/frontend/
still picks up skills defined at the root. When you
move the session with
/cd
on v2.1.246 or later, Claude Code adds the new directory’s project skills.
In a session running in a linked
git worktree
that you created with
--worktree
or
git worktree add
, Claude Code searches parent directories only up to the worktree root. On Claude Code v2.1.277 or later, when the worktree checkout has no
.claude/skills
directory at its root, Claude Code loads the main checkout’s project skills instead. See
What worktrees share with the main checkout
.
Skills in a
.claude/skills/
directory below where you started don’t load at startup. They load the first time Claude reads or edits a file in that subdirectory and stay available for the rest of the session. Until then they don’t appear in the
/
menu and you can’t invoke them by name. To load them sooner, run
/add-dir
with the subdirectory’s path, which requires Claude Code v2.1.257 or later. For a worktree session that you start from the desktop app, see
What worktrees share with the main checkout
.
When a nested skill’s directory name matches another skill’s name, both stay available. With a
deploy
skill at the repository root and another in
apps/web/.claude/skills/
:
/deploy
runs the root skill. Claude Code also lists the directory-qualified variants for Claude, with an instruction to invoke the one whose directory holds the files it’s working on, so the nested skill still applies to work in
apps/web/
.
/apps/web:deploy
runs the nested skill on its own. Its description names the directory it applies to.
​
Load skills from a directory outside the project
When you add a directory with
--add-dir
or
/add-dir
, Claude Code loads the skills in that directory’s
.claude/skills/
, along with its
.claude/commands/
and
.claude/agents/
. Directories the Agent SDK adds through
additionalDirectories
in TypeScript or
add_dirs
in Python load the same way, because the SDK passes them as
--add-dir
. The
permissions.additionalDirectories
setting in
settings.json
grants file access only and loads none of these.
Claude Code watches
.claude/skills/
in a directory you pass with
--add-dir
at launch, as
Edit a skill during a session
describes. It doesn’t watch the added directory’s
.claude/commands/
or
.claude/agents/
, so restart the session after changing a file there.
These loads depend on the
project
setting source
, which is on by default. A
strictPluginOnlyCustomization
policy,
bare mode
, and
--safe-mode
each restrict them further, as those pages describe. See
Additional directories grant file access, not configuration
for the full table of what an added directory loads, including
CLAUDE.md
and plugin settings.
​
Run a same-named skill from an added directory
An added directory’s skill gets a prefix when its folder name clashes with an enterprise, personal, or project skill, or one in a directory added earlier. To run it, type
/<prefix>:<skill-name>
at the Claude Code prompt. The
/
menu lists the skill under its prefixed name, and
How a skill gets its command name
describes where the prefix comes from. That name requires Claude Code v2.1.309 or later.
For example, with
--add-dir ../cli
and a
verify
skill in both your project and
../cli
:
/verify
runs your project’s skill
/cli:verify
runs the skill from
../cli
​
Resolve skills that share a name
When two skills share a directory or file name, where each one came from decides which one
/name
runs. For a name set by the frontmatter
name
field, see
How a skill gets its command name
.
Same name in
Which one runs
Two of enterprise, personal, and project
Enterprise over personal, and personal over project. With
deploy
in both
~/.claude/skills/
and the project’s
.claude/skills/
,
/deploy
runs the personal one
Any of those locations and a
bundled skill
Your skill replaces the bundled command, but not its aliases. A project
code-review
skill replaces
/code-review
, and the bundled alias
/review
never runs your skill
Any of those locations and a
built-in command
In a local terminal session, your skill replaces the built-in command, but not its aliases. A project
usage
skill replaces
/usage
, and the built-in alias
/cost
still runs the built-in command
A skill and a file in
.claude/commands/
The skill
A project-root skill and a nested skill
Both load. See
monorepos and subdirectories
An enterprise, personal, or project skill and a skill in an
added directory outside the project
The enterprise, personal, or project skill, while the added directory’s skill runs under a prefixed name. See
run a same-named skill from an added directory
Two
added directories
outside the project
The skill from the directory added first, in
--add-dir
or
/add-dir
order. The other runs under a
prefixed name
A plugin skill and a skill at any of the locations above
Both load, because plugin skills are namespaced as
/plugin-name:skill-name
Any of the above and the short name of a skill
synced from your claude.ai account
The other skill or command. The synced skill is then listed and runs only under its full name. See
When a synced skill name matches another command
​
Use skills in Cowork and cloud sessions
Cowork
sessions and
cloud sessions
, including
cloud scheduled tasks
, don’t read
~/.claude/skills/
on your machine. Both interactive and scheduled Cowork sessions load the skills enabled for your claude.ai account, synced at session start. Manage them from
Customize
in the Desktop app sidebar or from the skills settings on claude.ai.
If a skill exists only in
~/.claude/skills/
on your machine, Claude Code reports that the skill was not found when a
cloud scheduled task
invokes it. This happens because each run starts as a fresh cloud session. To make a personal skill available in these sessions:
For Cowork sessions, cloud sessions, and cloud threads in a
project
, enable the skill for your claude.ai account. In a project’s cloud thread, skills committed to a repository’s
.claude/skills/
aren’t available.
Some sessions in a self-hosted environment
don’t load your account’s skills.
For cloud sessions other than project threads, you can instead commit the skill to the repository’s
.claude/skills/
. Plugins declared in the repository’s
.claude/settings.json
and plugins enabled only in your user settings
don’t load in cloud sessions
.
Desktop scheduled tasks
run locally on your machine, so they do load
~/.claude/skills/
.
​
Skills synced from claude.ai
This section applies to you if you use Cowork or cloud sessions, or sign in to Claude Code in your terminal with a claude.ai account. In those sessions, Claude Code loads the skills enabled for your claude.ai account, with no setup on your part, as
Where synced skills load
describes. Those skills include the ones you create or turn on in your claude.ai settings, skills your organization provides there, and Anthropic’s built-in skills such as
pdf
and
xlsx
.
Claude Code downloads a synced skill from your account rather than reading a file you wrote on the machine where the session runs, so it applies rules to synced skills that don’t apply to the skills you store in the
skills locations
.
​
Where synced skills load
In a Cowork or cloud session, Claude Code loads the skills enabled for your claude.ai account, and
Skills in Cowork and cloud sessions
says how to choose which skills those sessions get.
In your terminal, Claude Code syncs those skills in sessions where you sign in with your claude.ai account. When the session starts, Claude Code downloads your account’s skills into
~/.claude/skills/synced/
in the background, then checks claude.ai for changes while the session runs. When a check finds that a skill was added, edited, or turned off on claude.ai, Claude Code adds, updates, or removes it in the running session without a restart. Syncing in terminal sessions requires Claude Code v2.1.273 or later.
The checks run less often while the session is idle:
While you or Claude work in the session
: a check runs about every 10 minutes.
While the session is idle
: a check runs about every 40 minutes. When you type in the session again, Claude Code checks within a few minutes if the last check was more than 10 minutes ago.
The sync never delays startup, because Claude waits for a skill’s download only when it invokes that skill. A short
non-interactive
run can therefore finish before a newly added skill downloads, in which case a later session downloads it. To make a non-interactive run download your skills and wait for the list before it answers the prompt, set
CLAUDE_CODE_SYNC_SKILLS
to
1
. Before v2.1.273, terminal sessions downloaded them only in a
-p
run with this variable set.
Claude Code syncs only in a session that signs in with your claude.ai account and
fetches feature flags from Anthropic
. It doesn’t sync in these sessions:
A session that doesn’t use a sign-in stored by
/login
, such as one that authenticates with an API key, or one where
ANTHROPIC_AUTH_TOKEN
,
CLAUDE_CODE_OAUTH_TOKEN
, or an
apiKeyHelper
script supplies the credential
A session that doesn’t fetch feature flags, such as one on Amazon Bedrock or one where you set
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
A session in
bare mode
or one you start with
--safe-mode
A session where your organization’s managed settings
lock skills to plugin sources
, or one you start with a
--setting-sources
list that leaves out
user
If you sign in with
/login
during a session, restart Claude Code to start syncing.
Skills that an earlier session synced stay on disk. Claude Code loads them in later sessions signed in to the same account, even when it can’t reach claude.ai.
Claude Code downloads synced skills and never uploads them. If you or Claude edit a file under
~/.claude/skills/synced/
, the change isn’t saved to your claude.ai account, and a later sync can overwrite or remove it. To change a synced skill, update it on claude.ai; the next sync downloads the new version.
To see which skills synced, run
/skills
. The menu lists them under
claude.ai sync
.
Some of Anthropic’s skills, such as
pdf
and
xlsx
, always sync. For the rest, turn a skill on or off in your skills settings on claude.ai to change whether it syncs.
To stop syncing on a machine, set
syncClaudeAiSkills
to
false
in your user settings. Claude Code stops downloading, and the next time it starts it moves the skills it already synced to
~/.claude/skills/.trash/
and no longer loads them. Your organization can turn syncing off for everyone by turning off Skills on claude.ai. To stop syncing while leaving Skills on, it can set the same key in
managed settings
.
If your organization turns Skills off on claude.ai, Claude Code removes the downloaded skills and they stop loading. The removed skills move to
~/.claude/skills/.trash/
, where you can recover the files until the
retention sweep
deletes them. Once your organization turns Skills back on, Claude Code downloads the skills you enabled at the next sync.
​
When a synced skill name matches another command
You can invoke a synced skill by its short name,
/<name>
, or by its full name,
/anthropic-skills:<name>
. When another command uses the short name,
/<name>
runs the other command, and the synced skill runs only as
/anthropic-skills:<name>
. With a local
deploy
skill and a synced
deploy
,
/deploy
runs the local skill and
/anthropic-skills:deploy
runs the synced one. Before v2.1.269, a synced skill had only its short name.
In the
/
menu,
/skills
, and
/context
, a synced skill appears under its short name, or under its full name while another command uses the short name. Run
/skills
in your session. A note under the list explains each synced skill that lost its short name. If one of your personal skills or command files in
~/.claude/
uses the name, the note also says what to rename or delete to free it.
From v2.1.269 through v2.1.280, these lists showed every synced skill under its full name, and
/skills
had no such note; both changed in v2.1.281.
The command that uses the short name can be any of these:
A built-in command or a
bundled skill
, including one that’s unavailable in your session, for example after you turn bundled skills off
A skill at any
local level
or a file in
.claude/commands/
A plugin skill
An
MCP prompt
Claude Code labels synced skills so you can tell where they came from. The
/skills
menu and
/context
group synced skills under
claude.ai sync
, and the
/
command menu marks them as coming from claude.ai.
When it compares names, Claude Code ignores case, spacing, and invisible characters, and treats compatibility forms such as fullwidth letters and dash variants as their plain equivalents. For example, a synced skill named
Commit
and a local skill named
commit
count as the same name, so
/commit
keeps running your local skill.
A name that differs only by a look-alike letter from another alphabet counts as a different name, and the
claude.ai sync
label is how you tell the two apart. These checks and labels require Claude Code v2.1.228 or later.
​
Names reserved for synced skills
Claude Code reserves the name
anthropic-skills
, and every name inside that namespace such as
anthropic-skills:pdf
, for skills synced from claude.ai, so a synced skill’s full name never runs anything else. The name is reserved in every session, whether or not you sign in with a claude.ai account.
A skill folder, a frontmatter
name
, a file or subfolder in
.claude/commands/
, or a
saved workflow
: it doesn’t load. A
startup notice
names the first item to rename or edit.
A plugin named
anthropic-skills
: it loads. When one of its skills and a synced skill are both named
<name>
,
/anthropic-skills:<name>
runs the synced skill.
An MCP server named
anthropic-skills
: it connects and its tools work, but
its prompts don’t appear as commands
. Rename the server in your MCP configuration to list them.
​
How Claude Code handles the frontmatter of a synced skill
Claude Code applies two rules to a synced skill’s frontmatter:
The frontmatter applies in every kind of session, so an
allowed-tools
grant goes through the normal
permission flow
. If your organization sets
allowManagedPermissionRulesOnly
, the grant
doesn’t apply
.
Claude Code sanitizes the display text the skill supplies, such as its description. It removes control characters, and in text that reaches Claude, such as the description, it also escapes angle brackets so the text can’t imitate Claude Code’s internal formatting. This sanitization requires Claude Code v2.1.228 or later.
​
How Claude Code handles the body of a synced skill
What Claude Code does with a synced skill’s body depends on where the session runs:
In a cloud session, the body keeps the behavior a local skill has, because the session runs in an isolated container.
In a Cowork session on your desktop, the body keeps the behavior a local skill has, except that Claude Code replaces every
!
command line with the
disableSkillShellExecution
placeholder
, as it does for every skill you supply there.
In any other session on your machine, Claude Code doesn’t run
!
commands
, doesn’t attach the files that
@
references name the way it does for a local skill, and doesn’t substitute the
${CLAUDE_PROJECT_DIR}
and
${CLAUDE_SESSION_ID}
placeholders, so the
@
references and both placeholders reach Claude as literal text. A
!
command line reaches Claude as literal text too, or as that placeholder when
disableSkillShellExecution
is on. This handling requires Claude Code v2.1.228 or later.
​
Edit a skill during a session
Claude Code watches skill directories for file changes, except in
bare mode
. When you add, edit, or remove a skill under
~/.claude/skills/
, the project
.claude/skills/
, or a
.claude/skills/
inside an
--add-dir
directory, Claude Code picks up the change within the current session, without a restart.
If you create a top-level skills directory that didn’t exist when the session started, run
/reload-skills
to pick up the skills you put there. Claude Code isn’t watching that directory yet, so run
/reload-skills
again after each later change there.
Live change detection covers
SKILL.md
text only. For a skill folder that is also a
plugin
, changes to
hooks/
,
.mcp.json
,
agents/
, and
output-styles/
need
/reload-plugins
to take effect.
​
Remove a skill
How you remove a skill depends on where it came from:
Personal or project skill
: delete the skill’s directory,
~/.claude/skills/<skill-name>/
or
.claude/skills/<skill-name>/
. Claude Code
drops it from
/skills
in the current session
; content Claude Code already loaded from it follows the
skill content lifecycle
.
Enterprise skill
: an administrator deletes the skill’s directory from
.claude/skills/
inside the
managed settings directory
, for example
/etc/claude-code/.claude/skills/<skill-name>/
on Linux.
Plugin skill
: disable or uninstall the plugin that provides it, from the
/plugin
menu or with
/plugin uninstall <plugin-name>@<marketplace-name>
. Claude Code unloads the plugin’s skills when
the change applies
or when you restart.
Skill synced from claude.ai
: turn the skill off for your claude.ai account, in the same place you
enabled it
. Claude Code removes it from
~/.claude/skills/synced/
the next time it
syncs your skills
. If you delete the directory by hand instead, the next sync downloads it again while the skill stays enabled on claude.ai.
Bundled skill
: set
disableBundledSkills
to
true
to turn off bundled skills, or set one skill to
"off"
in
skillOverrides
to hide it.
To keep a personal or project skill but stop Claude from invoking it on its own, set
disable-model-invocation: true
in its frontmatter, or
"user-invocable-only"
in
skillOverrides
when you don’t want to edit the file.
​
Configure skills
Skills are configured through YAML frontmatter at the top of
SKILL.md
and the markdown content that follows.
​
Types of skill content
Skill files can contain any instructions, but thinking about how you want to invoke them helps guide what to include:
Reference content
adds knowledge Claude applies to your current work. Conventions, patterns, style guides, domain knowledge. This content runs inline so Claude can use it alongside your conversation context.
---
name
:
api-conventions
description
:
API design patterns for this codebase
---
When writing API endpoints
:
-
Use RESTful naming conventions
-
Return consistent error formats
-
Include request validation
Task content
gives Claude step-by-step instructions for a specific action, like deployments, commits, or code generation. These are often actions you want to invoke directly with
/skill-name
rather than letting Claude decide when to run them. Add
disable-model-invocation: true
to prevent Claude from triggering it automatically. The example below adds
context: fork
, which runs the skill in its own subagent context; see
Run skills in a subagent
.
---
name
:
deploy
description
:
Deploy the application to production
context
:
fork
disable-model-invocation
:
true
---
Deploy the application
:
1. Run the test suite
2. Build the application
3. Push to the deployment target
Keep the body itself concise. Once a skill loads, its content
stays in context across turns
, so every line is a recurring token cost. State what to do rather than narrating how or why, and apply the same conciseness test you would for
CLAUDE.md content
.
​
Frontmatter reference
Configure a skill with YAML
frontmatter
between
---
markers at the top of
SKILL.md
, and write the skill’s instructions as Markdown after the closing
---
. Field names use lowercase words separated by hyphens, except
when_to_use
. A
command file
in
.claude/commands/
accepts the same fields except
name
and
paths
. This example sets four fields:
---
name
:
my-skill
description
:
What this skill does
disable-model-invocation
:
true
allowed-tools
:
Read Grep
---
Your skill instructions here...
All fields are optional. Only
description
is recommended so Claude knows when to use the skill. A field name must match the table exactly, hyphens included: Claude Code ignores a field it doesn’t recognize without reporting an error. Boolean fields accept
yes
,
no
,
on
,
off
,
1
, and
0
in any letter case, in addition to
true
and
false
.
Claude Code reads the frontmatter only when the opening
---
is the file’s first line. Otherwise it treats the whole file,
---
markers included, as skill content. If the YAML between the markers doesn’t parse, the skill still loads with no fields set; see
Skill not triggering
to find and fix the error.
Field
Required
Description
name
No
Command name shown in the
/
menu. Defaults to the directory name. See
How a skill gets its command name
for how the field interacts with the name you type to invoke the skill.
description
Recommended
What the skill does and when to use it. Claude uses this to decide when to apply the skill. If omitted, uses the first non-empty line of the markdown content. Put the key use case first: the combined
description
and
when_to_use
text is truncated at 1,536 characters in the skill listing to reduce context usage. Angle brackets in the text
show as
&lt;
and
&gt;
.
when_to_use
No
Additional context for when Claude should invoke the skill, such as trigger phrases or example requests. Appended to
description
in the skill listing and counts toward the 1,536-character cap.
argument-hint
No
Hint shown during autocomplete to indicate expected arguments. Example:
[issue-number]
or
[filename] [format]
.
arguments
No
Named positional arguments for
$name
substitution
in the skill content. Accepts a space-separated string or a YAML list. Names map to argument positions in order.
disable-model-invocation
No
Set to
true
to prevent Claude from automatically loading this skill. Use for workflows you want to trigger manually with
/name
. Also prevents the skill from being
preloaded into subagents
and from running when a
session-scoped scheduled task
fires with the skill as its prompt. Default:
false
.
user-invocable
No
Set to
false
when only Claude should invoke the skill: Claude Code hides it from the
/
menu and doesn’t run it when you type
/name
. Use for background knowledge users shouldn’t invoke directly. Default:
true
.
allowed-tools
No
Tools Claude can use without asking permission during the turn that invokes this skill. The grant clears when you send your next message. Accepts a space- or comma-separated string, or a YAML list. See
Pre-approve tools for a skill
.
disallowed-tools
No
Tools removed from Claude’s available pool while this skill is active. Use for autonomous skills that should never call certain tools, such as
AskUserQuestion
for a background loop. Accepts a space- or comma-separated string, or a YAML list. The restriction clears when you send your next message. Like deny rules, the field can’t remove
EndConversation
while any other tool remains.
model
No
Model to use when this skill is active. The override applies for the rest of the current turn and isn’t saved to settings. The session model resumes when you send your next prompt. Accepts the same values as
/model
, or
inherit
to keep the active model. A value excluded by your organization’s
availableModels
allowlist isn’t used, and the session keeps its current model. In
auto mode
, and in
plan mode while the classifier reviews commands
, a model that auto mode doesn’t support also isn’t used, and the session keeps its current model. With
context: fork
, the value sets the
forked subagent’s model
instead, and an excluded value follows the
same rules as a subagent model override
.
effort
No
Effort level
for the rest of the current turn. Overrides the session effort level, but not the
CLAUDE_CODE_EFFORT_LEVEL
environment variable. With
context: fork
, the value sets the forked subagent’s effort level instead. When you omit it, the level comes from the
effort resolution order
. Options:
low
,
medium
,
high
,
xhigh
,
max
; available levels depend on the model.
context
No
Set to
fork
to run in a forked subagent context. See
Run skills in a subagent
.
agent
No
Which subagent type to use when
context: fork
is set.
background
No
Only applies with
context: fork
. Set to
false
to wait for the forked subagent’s result in the turn that invoked the skill, instead of
running it in the background
. Default:
true
.
hooks
No
Hooks that Claude Code registers when the skill is invoked and keeps running for the rest of the session. See
Hooks in skills and agents
for the configuration format, the
once
option, and the
limits on skill hooks
.
paths
No
Glob patterns that limit when this skill is activated. Accepts a comma-separated string or a YAML list. When set, Claude loads the skill automatically only when working with files matching the patterns. Patterns are relative to Claude’s current working directory, and files outside that directory don’t match. Uses the same glob format as
path-specific rules
.
shell
No
Shell to use for
!`command`
and
```!
blocks in this skill. Accepts
bash
(default) or
powershell
. Setting
powershell
runs inline shell commands via PowerShell when the
PowerShell tool
is enabled: it’s on by default on Windows without Git Bash, on by default with Git Bash for claude.ai and Console accounts, and needs
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
in Amazon Bedrock, Google Cloud’s Agent Platform, and Microsoft Foundry sessions and on macOS, Linux, and WSL. Set it to
0
to turn the tool off.
metadata
No
Free-form YAML map for your own key-value data, such as entitlement or catalog fields, read by your own tooling from
SKILL.md
. Claude Code doesn’t act on its contents, and drops a value that isn’t a map. Don’t reuse frontmatter field names such as
paths
as keys.
license
No
License covering the skill. Part of the
Agent Skills
spec; see
Using skill frontmatter outside Claude Code
. Claude Code accepts the field but doesn’t act on it.
compatibility
No
Environment requirements for the skill, such as intended products or system prerequisites, as defined by the
Agent Skills
spec; see
Using skill frontmatter outside Claude Code
. Accepts a string of up to 500 characters. Claude Code accepts the field but doesn’t act on it.
​
Using skill frontmatter outside Claude Code
Claude Code accepts every field in the table above. Outside Claude Code, you can use only the fields in the
Agent Skills
spec:
Distribution path
Frontmatter fields you can use
Claude Code skills at
any level
, including
plugin
skills
Every field in the table above
claude.ai skill uploads, the Skills API, and packaging with
package_skill.py
from
anthropics/skills
name
,
description
,
license
,
compatibility
,
metadata
,
allowed-tools
When you enable a personal skill for your claude.ai account, for example to use it in
Cowork and cloud sessions
and scheduled tasks, you upload it to claude.ai. The same rules apply to that upload.
If you include any field the spec doesn’t allow, packaging or upload fails with a hard error instead of ignoring the field:
Unexpected key(s) in SKILL.md frontmatter: argument-hint. Allowed properties are: allowed-tools, compatibility, description, license, metadata, name
Restricting frontmatter to the spec’s six fields avoids the unexpected-key error above. The
Agent Skills spec
and the
Skills API requirements
define everything else those paths validate. Claude Code-only body features, such as
dynamic context injection
, don’t function in claude.ai chat or through the API. Claude Code accepts all six fields, so frontmatter that follows the spec loads in Claude Code without changes.
​
How a skill gets its command name
The command you type to invoke a skill comes from where the skill file lives and, for skill directories and plugin skills, from the frontmatter
name
field. In a personal or project skill directory,
name
sets the command that the
/
menu shows and that you type, unless another command already uses that name. The directory name also invokes the skill. In a plugin skill,
name
sets the last segment of the command and the plugin prefix stays in place.
The table below shows where the command name comes from for each layout:
Skill location
Command name source
Example
Skill directory under
~/.claude/skills/
or
.claude/skills/
Frontmatter
name
or the directory name
.claude/skills/deploy-staging/SKILL.md
→
/deploy-staging
, or
/deploy
with
name: deploy
Nested
.claude/skills/
directory, when the directory name clashes with another skill
Subdirectory path relative to the working directory, then the skill directory name
apps/web/.claude/skills/deploy/SKILL.md
→
/apps/web:deploy
.claude/skills/
in an
added directory outside the project
, when the skill directory name clashes with an enterprise, personal, or project skill, or one in a directory added earlier
The added directory’s folder name, then the skill directory name. When two added directories share a folder name, the prefix starts with the parent folder’s name. Requires v2.1.309 or later
../cli/.claude/skills/verify/SKILL.md
with
--add-dir ../cli
→
/cli:verify
. With
--add-dir ../a/cli --add-dir ../b/cli
, a
verify
skill in each, and none elsewhere, the one in
../a/cli
→
/verify
and the other →
/b/cli:verify
File under
.claude/commands/
File name without extension
.claude/commands/deploy.md
→
/deploy
File in a subdirectory of
.claude/commands/
Subdirectory path relative to
commands/
with each
/
replaced by
:
, then the file name without extension
.claude/commands/frontend/component.md
→
/frontend:component
Plugin
skills/
subdirectory
Frontmatter
name
or the directory name, namespaced by plugin
my-plugin/skills/review/SKILL.md
→
/my-plugin:review
, or
/my-plugin:fancy
with
name: fancy
Plugin root
SKILL.md
Frontmatter
name
, with the plugin directory name as a fallback
my-plugin/SKILL.md
with
name: review
→
/my-plugin:review
. See
a single skill at the plugin root
Skill
synced from claude.ai
The skill’s name on your claude.ai account, prefixed with
anthropic-skills:
Account skill
deploy
→
/anthropic-skills:deploy
, or
/deploy
while no other command uses that name
In a plugin skill, the frontmatter
name
replaces the directory name in the last segment of the command, so
my-plugin/skills/review/SKILL.md
with
name: fancy
becomes
/my-plugin:fancy
. The bare
/fancy
also invokes the skill unless another command already uses that name. If the
name
you write already starts with the plugin’s own prefix, Claude Code doesn’t add the prefix again on v2.1.246 or later. For example,
name: my-plugin:fancy
still becomes
/my-plugin:fancy
. From v2.1.216 through v2.1.245, Claude Code doubled the prefix when the
name
already carried it.
In
non-interactive sessions
, the names
help
and
feedback
aren’t reserved for their terminal-only built-in commands, so a plugin skill with one of those names keeps its bare command there. Every other terminal-only built-in’s name, such as
/login
, stays reserved even though the command can’t run in those sessions.
For a plugin-root
SKILL.md
, there is no skill directory to take the name from, so
name
supplies the whole final segment. Without a
name
field, Claude Code falls back to the plugin’s directory name.
​
Characters a skill name can’t hold
If a skill or custom command is missing from the
/
menu, or the menu doesn’t show a skill’s frontmatter
name
, check the name. Claude Code refuses a command name or a frontmatter
name
that contains characters such as these:
A zero-width space or a control character
A private-use or unassigned character, such as a glyph from an icon font
A character that changes the direction of the text around it
A blank other than one plain space between words, such as a no-break space, two spaces in a row, or a space at the start or end
<
or
>
A custom command or skill doesn’t load when Claude Code refuses its directory or file name. Rename that folder or file to remove the characters. A skill still loads when these characters are only in a plugin skill folder’s name or in its frontmatter
name
:
Folder in a plugin’s
skills/
directory or its manifest’s
skills
paths
: you don’t need to rename the folder. These characters become hyphens in the skill’s command name, so type the command with the hyphens.
Frontmatter
name
: the
/
menu doesn’t show the
name
value and typing it doesn’t invoke the skill. Edit the
name:
line to remove the characters.
To find out which name Claude Code refused, start it with
claude --debug
from your shell and search the
debug log
for
[names]
. In an interactive session, a
startup notice
also tells you that names were refused. After a rename or a
name:
edit, restart the session, unless the file is in a directory Claude Code
watches for changes
.
​
Available string substitutions
Skills support string substitution for dynamic values in the skill content:
Variable
Description
$ARGUMENTS
All arguments passed when invoking the skill. When no placeholder receives an argument, Claude Code appends them as
ARGUMENTS: <value>
. See
Pass arguments to skills
.
$ARGUMENTS[N]
Access a specific argument by 0-based index, such as
$ARGUMENTS[0]
for the first argument.
$N
Shorthand for
$ARGUMENTS[N]
, such as
$0
for the first argument or
$1
for the second.
$name
Named argument declared in the
arguments
frontmatter list. Names map to positions in order, so with
arguments: [issue, branch]
the placeholder
$issue
expands to the first argument and
$branch
to the second.
${CLAUDE_SESSION_ID}
The current session ID. Useful for logging, creating session-specific files, or correlating skill output with sessions.
${CLAUDE_EFFORT}
The current effort level:
low
,
medium
,
high
,
xhigh
, or
max
. Use this to adapt skill instructions to the active effort setting.
${CLAUDE_SKILL_DIR}
The directory containing the skill’s
SKILL.md
file. For plugin skills, this is the skill’s subdirectory within the plugin, not the plugin root. Use this in bash injection commands to reference scripts or files bundled with the skill, regardless of the current working directory.
${CLAUDE_PROJECT_DIR}
The project root directory. This is the same path
hooks
and MCP servers receive as
CLAUDE_PROJECT_DIR
. Use this to reference project-local scripts or files, such as
${CLAUDE_PROJECT_DIR}/.claude/hooks/helper.sh
, independent of where the skill is installed.
${CLAUDE_PLUGIN_ROOT}
The plugin’s installation directory. Substituted only in plugin skills. Use this to reference scripts or files bundled anywhere in the plugin, including resources shared between the plugin’s skills. See
plugin environment variables
.
${CLAUDE_PLUGIN_DATA}
The plugin’s
persistent data directory
, which survives plugin updates. Substituted only in plugin skills. Use this to reference installed dependencies, generated files, or caches that must outlive an update.
Claude Code substitutes
${CLAUDE_SKILL_DIR}
and
${CLAUDE_PROJECT_DIR}
in two places: the skill’s markdown content, and Bash rules in the
allowed-tools
frontmatter. In

## Source (settings): https://docs.claude.com/en/docs/claude-code/settings

Settings files and precedence - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
Settings are the JSON keys that change how Claude Code behaves: which model it starts with, what it can run without asking, which files it can’t read, how it looks in your terminal, and what your organization enforces.
To look up a specific key, go to
All settings
, which lists every key with the file you set it in, its default, and an example.
Claude Code reads settings from JSON settings files such as
~/.claude/settings.json
. It looks for them in a few locations, and
the file it reads a setting from decides who the setting applies to
. This page covers those files: which one to put a setting in, how to change a setting and confirm it applied, and which value Claude Code uses when the same key is set in more than one file.
Configure permissions
covers what Claude Code can run without asking and how to write
allow
,
ask
, and
deny
rules.
This page covers Claude Code running on your machine: the terminal, the
VS Code
and
JetBrains
extensions, and the
desktop app
, which all read the same settings files. A
cloud session
runs on a different machine and reads only some of them; see
Settings in cloud sessions
.
​
Settings files and who they affect
Claude Code reads settings from four files, and an organization can also deliver managed settings from the claude.ai console. Each source has a scope: the set of people and projects a setting saved in it applies to, whether that’s only you, everyone in a project, or everyone in your organization.
Scope
File
Who it affects
Use it for
User
~/.claude/settings.json
You, in every project on this machine
Personal preferences: theme, editor mode, default model, your own permission rules
Shared project
.claude/settings.json
Everyone working in the folder that contains it. In a git repository, commit it so teammates get it
Team permissions, hooks, plugins, and the environment variables the project needs
Project local
.claude/settings.local.json
You, in this one project only. Claude Code keeps it out of git when it creates the file; if you create it by hand, add it to
.gitignore
yourself
Personal overrides for one project, and testing before you share
Managed
managed-settings.json
and other
managed sources
Everyone your organization deploys it to;
Settings precedence
says what can override it
Security policy and compliance requirements
In the File column,
~/.claude
is the
.claude
folder in your home directory, and a bare
.claude
is the
.claude
folder inside your project.
​
Compare the scope of each settings file
Suppose you have three projects on your machine,
website/
,
api/
, and
acme-app/
, a teammate has their own clone of
acme-app/
, and you start a
cloud session
on
acme-app/
.
The graphic below shows which of those folders a setting applies in when you start Claude Code from them. Click a settings file to see the folders it reaches.
~/.claude/settings.json
: every project on your machine, and nothing on your teammate’s or in the cloud session
acme-app/.claude/settings.json
: your
acme-app/
. It reaches your teammate’s clone and the cloud session only if you commit the file to version control; until you do, it’s a file on your disk like any other and nobody else has it
acme-app/.claude/settings.local.json
: your
acme-app/
only. Claude Code adds it to your global git excludes the first time it writes the file, so it stays out of your commits; if you create the file by hand,
add it to
.gitignore
yourself
Managed settings
, whether a
managed-settings.json
file, an MDM policy, or
server-managed settings
from the claude.ai console: every project on every machine your organization deploys it to, or that you sign in to with your organization account. Only server-managed settings reach the cloud session
​
Find or create your settings files
Installing Claude Code doesn’t create any settings file. If your machine or project already has one, it came from one of these sources:
Managed
: your organization deploys it. You don’t create or edit it.
Shared project
: a project that already uses Claude Code may have one committed. If not, create it at
.claude/settings.json
in the project folder.
User
and
Project local
: create them yourself, or let Claude Code create them. It writes
~/.claude/settings.json
the first time you change an option in the
/config
menu that it stores in user settings, such as the theme, and
.claude/settings.local.json
the first time you give a standing approval on a permission prompt, such as “Yes, and don’t ask again” for a Bash command. A few
/config
options, including
Show tips
, save to
.claude/settings.local.json
instead of the user file.
On Windows,
~/.claude
means
%USERPROFILE%\.claude
. To keep the home-directory files somewhere else, set
CLAUDE_CONFIG_DIR
; Claude Code then stores your settings, session history, and plugins there instead.
Claude Code also keeps a fifth file,
~/.claude.json
, that it writes for itself; you don’t need to edit it. It holds your account details,
MCP server
configurations, per-project state such as trust decisions, and the
global config keys
that
/config
writes for you.
​
Share settings with your team
Commit
.claude/settings.json
so everyone who clones the repository gets the same permissions, hooks, and plugins. Each teammate can still override it for themselves in their own
.claude/settings.local.json
, so personal exceptions don’t need a commit. For a complete team file, see
a team’s shared settings
.
Some of what you commit waits until each teammate
trusts the folder
, and a few keys never take effect from a repository file;
Troubleshoot a setting that doesn’t apply
covers both.
​
Keep personal settings out of a repository
To change a setting for yourself in one project without changing it for your teammates, save it in
.claude/settings.local.json
inside the project. Claude Code applies that file over the committed
.claude/settings.json
, so if your team’s file sets
"model": "claude-sonnet-5"
and you want Opus, put
"model": "claude-opus-5-5"
in your local file and only your sessions change.
Claude Code also writes to this file, keeps it out of your commits, and applies its allow rules without the trust step:
Claude Code writes it too.
When Claude asks permission to run a Bash command and you choose “Yes, and don’t ask again”, Claude Code saves that
permission approval
here as an
allow
rule.
You don’t need to gitignore it yourself, unless you created it by hand.
The first time Claude Code writes the file in a git repository that doesn’t already ignore it, it adds
**/.claude/settings.local.json
to your global git excludes file, so the file stays out of your commits in every repository. That file is
core.excludesFile
when your global git config sets it to an absolute or
~
-prefixed path; otherwise it’s
$XDG_CONFIG_HOME/git/ignore
, or
~/.config/git/ignore
when
XDG_CONFIG_HOME
is unset. If you created the file by hand and Claude Code hasn’t written to it yet, add it to
.gitignore
yourself.
Its allow rules don’t wait for trust while the file stays untracked.
Because the file is yours and not the repository’s, Claude Code applies its
allow
rules without the
workspace trust
step it requires for the committed file. If the file is tracked by git, the trust step applies to it too; see
When your local settings file needs trust
.
​
Where Claude Code keeps the local file in a git repository
When Claude asks permission to run a Bash command and you choose “Yes, and don’t ask again”, Claude Code saves that approval as an
allow
rule in
.claude/settings.local.json
. If you start Claude Code in a subdirectory of a git repository, it reads and writes that file at the repository root and applies the approval across the whole repository. In a
worktree
, it uses the file at the main checkout’s root.
Two rules qualify the root location:
When the file stays with
.claude/settings.json
instead
: outside a git repository, when the repository root is your home directory, on Windows, or when the repository root or its
.git
or
.claude
entry isn’t owned by your user.
Paths in the file don’t anchor at the repository root
: a permission rule that starts with
/
or a relative sandbox path
anchors at the session’s primary working directory
instead.
Before v2.1.211, Claude Code kept the file in the starting directory. It still reads a file an earlier version left there alongside the root file; where both set the same key, the root’s value applies, and permission rules from both files apply. The Agent SDK’s
resolveSettings()
helper always reads the file from the starting directory.
Claude Code reads the shared
.claude/settings.json
from the session’s
primary working directory
, so to use a file committed at the repository root, start Claude Code there. After you
move the session with
/cd
, Claude Code reads both project files from the new directory instead, placing the local file by the same rules. Reading them from the directory you moved to requires Claude Code v2.1.246 or later. For a worktree session that you start from the desktop app, see
What worktrees share with the main checkout
.
​
Check what your organization enforces
If your organization manages Claude Code, some settings are decided for you and nothing you put in your own files changes them. To see which, run
/status
: the
Setting sources
line names the managed source that applies to you. Managed settings apply wherever Claude Code runs on this machine;
What a developer can change
covers local admin rights and tools other than Claude Code.
Managed settings reach you through the
delivery mechanisms
on the managed settings page, most commonly:
Server-managed settings
, which Claude Code fetches from the claude.ai admin console or a self-hosted
Claude apps gateway
MDM or OS-level policies, and
managed-settings.json
files in a system directory
An embedding host such as Claude Desktop, through the SDK
managedSettings
option; see
Control policy from an embedding host
In a
Cowork
session that runs on your machine in the Claude Desktop app, Claude Code doesn’t fetch server-managed settings from the claude.ai admin console, and it reads policy deployed to your device unless your organization’s Claude Desktop configuration sets
requireCoworkFullVmSandbox
.
Where and when a policy applies
covers Cowork and cloud sessions.
If you’re the administrator,
Set up Claude Code for your organization
walks through choosing what to enforce, and
Deploy managed settings
covers delivery and how to confirm a policy is in force. For the warning the managed settings editor in the claude.ai admin console can show, see
Configure server-managed settings
.
​
Change a setting
You can change a setting from the
/config
menu, by editing a settings file, or for one session from the command line.
Claude Code’s system prompt isn’t published. To give Claude standing instructions, use
CLAUDE.md
files
or the
--append-system-prompt
flag.
​
Use the /config menu
Run
/config
inside Claude Code and open the
Config
tab. It lists a short set of personal options such as theme, editor mode, and verbose output, not every settings key. Select an option to change it; Claude Code saves it for you:
Most options
:
~/.claude/settings.json
A few options, such as Show tips
:
.claude/settings.local.json
The
global config options
:
~/.claude.json
To set one option without the menu, pass
key=value
, such as
/config verbose=true
.
/config
is part of the terminal interface. The
VS Code
chat panel and the
desktop app
don’t open it; change settings there by editing a settings file or through those apps’ own settings.
​
Edit a settings file
Open the settings file for the scope you want in your editor and add or change a key. Settings files are strict JSON: a
//
comment or a trailing comma is a syntax error, and Claude Code reports the file as a
Settings Error
at the next start. For example, to let Claude Code run your lint and test commands without asking and stop it reading
.env
files, add this to
~/.claude/settings.json
:
~/.claude/settings.json
{
"$schema"
:
"https://json.schemastore.org/claude-code-settings.json"
,
"permissions"
: {
"allow"
: [
"Bash(npm run lint)"
,
"Bash(npm run test *)"
],
"deny"
: [
"Read(./.env)"
,
"Read(./.env.*)"
]
}
}
Each entry under
permissions
is a rule that names a tool and what it may do;
Configure permissions
explains the syntax. The
$schema
line points to the
published JSON schema
for Claude Code settings, which gives you autocomplete and inline validation in VS Code, Cursor, and any other editor that supports JSON schema. The schema can lag behind the newest CLI releases, so a validation warning on a recently documented key doesn’t mean your configuration is invalid.
After you save, run
/status
inside Claude Code to confirm the file loaded;
Confirm what loaded
says what the
Setting sources
line shows and how a broken file is reported.
For a complete personal file, team file, and organization file, each shown with a comment on every key it sets, see the
example settings files
.
​
Change a setting for one session
To try a value without saving it, set it when you start Claude Code. The value applies to that session and your settings files stay as they were. You have three ways to do it:
--settings
: pass a key as JSON, inline or as a path to a file. Claude Code applies it above your user, project, and local files and below managed settings. It can set any key your user settings file can set; it can’t set
Managed
or
Global config
keys.
A flag for that key
: some keys have their own flag, such as
--model
for
model
and
--effort
for
effortLevel
and
modelSettings
.
An environment variable
: export the key’s paired variable before you run
claude
, such as
ANTHROPIC_MODEL
for
model
.
Each key’s entry on the
settings reference
lists its per-session overrides and which one takes precedence, so check the entry for the key you want to change.
Commands you run inside a session mostly save your choice: when you change a setting in
/config
, Claude Code writes it to your settings files, and
/model
saves the value as your default for new sessions.
If you press
s
in the
/model
picker, Claude Code switches the model without saving it as your user default.
Adjust effort level
says which
/effort
picks Claude Code saves as your default for the model you’re using and which apply to the current session only.
For example, to start one session on Opus without changing your default:
claude
--settings
'{"model": "claude-opus-5-5"}'
​
When edits take effect
Claude Code watches your settings files and reloads them when they change, so it applies most edits to the running session without a restart, including edits to
permissions
,
hooks
, and credential helpers such as
apiKeyHelper
. Claude Code also loads a settings file you create mid-session if its folder existed when the session started. For the project’s
.claude/
folder, it loads the file even when you create the folder in the same session.
The reload covers user, project, local, and managed settings, and Claude Code runs the
ConfigChange
hook
for each settings-file change it detects, not for managed settings that arrive from MDM or the claude.ai console. Managed settings that arrive through MDM or from the claude.ai console reach a running session on a schedule rather than on save; the
delivery table
gives it per source.
Claude Code reads some keys only once, at session start, so an edit to one of them doesn’t reach the running session. Admin-side keys that also wait for a restart, such as
requiredMinimumVersion
, are listed under
where and when a policy applies
. The ones you’re most likely to edit mid-session:
model
: use
/model
to switch mid-session. Each model has its own prompt cache, so the first request after a switch re-reads the whole conversation uncached; see
Switching models
effortLevel
and
modelSettings
: use
/effort
to change effort mid-session
​
Confirm what loaded
Run
/status
inside Claude Code to see which settings sources are active. The
Status
tab includes a
Setting sources
line that lists each settings file Claude Code loaded for the current session, such as
User settings
or
Project local settings
. When
managed settings
are in effect, the managed settings entry shows in parentheses how they reached your machine.
The line confirms which files Claude Code read; it doesn’t show which file supplied each key. To list entries Claude Code rejected, run
claude doctor
; for a model that project or managed settings set, the startup header names the file that set it.
/status
and
/config
open the same dialog on different tabs, and the
Config
tab isn’t a view of your
settings.json
contents.
​
Fix a broken settings file
If you mistype JSON or set a key to a value Claude Code doesn’t accept, Claude Code tells you at the start of an interactive session. What it shows depends on how much of the file is affected:
Settings Error
: a user, project, or local file has invalid JSON or a value the schema rejects. At the start of an interactive session Claude Code shows a dialog that lets you fix the file with Claude’s help, exit, or continue without the broken settings.
Settings Warning
: only individual entries fail, such as a malformed permission rule or an unknown hook event name. Claude Code skips those values and keeps the rest of the file in effect.
Managed settings
: Claude Code keeps enforcing the rest of the file.
Invalid entries in managed settings
says what it drops and which keys fall back to a stricter value until you fix them. For a managed settings document that isn’t valid JSON, see
Managed settings document could not be parsed
.
Configuration error
:
~/.claude.json
can’t be parsed. Claude Code copies the broken file to
~/.claude/backups/.claude.json.corrupted.<timestamp>
and asks whether to exit and fix it by hand or reset to the default configuration; a
-p
run prints the error and exits. To recover your previous state, copy back one of the five most recent
.claude.json.backup.<timestamp>
files in
~/.claude/backups/
, which Claude Code saves before it writes the file.
After you continue, run
/status
to see the affected files and
claude doctor
for the details of each error.
A
-p
run shows no dialog. Unless
a managed settings document can’t be parsed
, Claude Code skips the broken file or values and continues with the rest, so after a
-p
run that ignores a setting, run
claude doctor
to see what it dropped.
​
Settings precedence
When the same key appears in more than one place, Claude Code uses the value from the highest level that sets it. The stack below shows the levels, highest on top; a key at a higher level overrides the same key anywhere below it.
In order, highest precedence first:
Managed settings
: settings your organization deploys, by a
managed-settings.json
file, an MDM policy, or
server-managed settings
from the claude.ai console. Nothing in your own settings files or
--settings
overrides a managed key, and a flag such as
--model
picks only from the models your organization allows. A managed
model
is a starting default, not a lock; the locks are
availableModels
and
deniedModels
. When your organization delivers more than one managed source, the rules for
precedence within the managed tier
say what Claude Code reads from each.
Command line
: JSON you pass with
--settings <file-or-json>
when you start
claude
, for that session only; see
Change a setting for one session
. A key you set there overrides the same key in your project and user settings files, and a key you leave out keeps its value from those files. Other flags, such as
--model
, set one thing for the session and aren’t part of this stack; a key’s entry on the
settings reference
says which flags override it.
Project local settings
(
.claude/settings.local.json
): your personal settings for this project.
Shared project settings
(
.claude/settings.json
): settings your team checks into source control.
User settings
(
~/.claude/settings.json
): your personal settings for every project.
Environment variables aren’t a level in this stack. When a behavior has both a shell variable and a settings key, which one applies is decided per pair, not by level:
ANTHROPIC_MODEL
exported in your shell applies over the
model
key from any file, while
ANTHROPIC_DEFAULT_MODEL
applies only when no file sets
model
. The
environment variables reference
says which keys have a pair and which one Claude Code reads first. An
env
block inside a settings file is an ordinary key and follows the levels above.
For a few security-sensitive keys, Claude Code honors a stricter value from a lower level over a managed value;
Exceptions to managed settings precedence
lists them.
​
Lists merge instead of overriding
When you set the same list key, such as
permissions.allow
, in more than one file, Claude Code combines the lists instead of picking one, so each file can add entries without removing another file’s. Four keys that hold model lists or per-model entries follow their own rules:
fallbackModel
is an ordered chain where position carries meaning, so Claude Code takes the whole value from the highest-precedence file that defines it.
modelPicker
holds one ordered list of rows plus a replace flag, so Claude Code never merges rows from two sources. It takes the whole value from the highest of managed settings,
--settings
, and user settings that defines it, and ignores the key in project and local settings. Requires Claude Code v2.1.242 or later.
availableModels
: when the managed settings Claude Code applies define it, Claude Code applies that list as-is and ignores entries you add in user, project, or local settings, unless an app that embeds Claude Code supplies its own model list; see
Exceptions to managed settings precedence
. Across managed sources the list never merges either;
how Claude Code combines managed sources
says which source’s list applies. Across non-managed scopes Claude Code merges the arrays as usual.
modelSettings
: Claude Code resolves it one model at a time, together with
effortLevel
. The
modelSettings
entry states which file’s value applies to a model.
​
Precedence examples
While Claude works, Claude Code shows a one-line tip under the spinner, such as “Use /config to change your default permission mode (including Plan Mode)”. Suppose you want those tips off, so you set
spinnerTipsEnabled
to
false
in
~/.claude/settings.json
. Each scenario below is something that can turn them back on, and what you can do about it.
​
Team settings override personal settings
Your team’s
.claude/settings.json
sets it to
true
. Claude Code uses the project value because shared project sits above user, so you see tips in that project and nowhere else.
You can get your value back: add
"spinnerTipsEnabled": false
to
.claude/settings.local.json
in that project. Project local sits above shared project, so your sessions there stop showing tips and your teammates’ sessions don’t change.
​
Organization settings override everything
Your organization’s managed settings set it to
true
. Nothing you put in user, project, or local settings turns tips off, and neither does
--settings
. Managed is the top level.
You can’t get your value back. Run
/status
to see which managed source applies, and ask your administrator if the policy should change.
​
The command line overrides your files for one session
You started the session with
claude --settings '{"spinnerTipsEnabled": true}'
. Command line sits above every file except managed, so that session shows tips even though your files say
false
.
You get your value back on the next session;
--settings
lasts one session and doesn’t write to any file.
​
A flag or environment variable sets the same thing
Some keys have a command line flag or an environment variable that overrides the settings value regardless of which file set it:
ANTHROPIC_MODEL
overrides the
model
setting, and
--model
overrides both for a session.
Whether you can get your value back depends on the key: unset the variable or drop the flag, and check the key’s entry on the
settings reference
and the variable’s row on the
environment variables reference
for which one Claude Code uses.
​
Troubleshoot a setting that doesn’t apply
When you set a key and Claude Code doesn’t behave as if you had, start with
/status
to see which files it loaded, then find your symptom below.
Debug your configuration
covers the wider checks, including a clean-configuration test.
​
A value you set is ignored
Something else is setting the same key, the file can’t set that value, or the file didn’t load:
A higher level sets it.
Another settings file, a
--settings
flag, or a managed source sets the key above yours; the
stack
says which. A flag or environment variable can also override the key on its own, decided key by key; the key’s entry on the
settings reference
says which one Claude Code uses, and the
env
entry
covers a managed
env
value versus a shell export.
A security key keeps its strict value.
For a few keys Claude Code honors the restrictive value from any file, so a project
true
for
disableClaudeAiConnectors
stays on; see
Exceptions to managed settings precedence
.
The file can’t set that value.
permissions.defaultMode
values
auto
and
bypassPermissions
don’t take effect from project or local settings; set them in user or managed settings instead, or pass
--permission-mode
for one session. Before v2.1.257,
bypassPermissions
took effect from any file.
A telemetry export variable in an
env
block doesn’t take effect from project or local settings either, apart from a few off values.
Variables Claude Code ignores in
env
lists the variables and those values.
The file is broken.
Invalid JSON or a rejected value makes Claude Code skip the file or the entry; see
Fix a broken settings file
.
​
A change you made in Claude Code is lost in new sessions
When you save a choice for new sessions from inside Claude Code, such as a default model with
/model
, Claude Code writes it to your user settings file,
~/.claude/settings.json
. If you can’t write to that file, for example because another tool generates it or links it to a read-only copy, the change applies to the current session and is gone in the next one. Set the key in the tool that generates the file, or replace the file with one you can write to.
If you can write to the file and the change still doesn’t last, check whether the change was
for one session only
or
a higher level sets the same key
. For the
model
key,
A new session starts on a different model than you picked
lists more causes.
​
A managed change hasn’t reached you
Managed sources reach a running session on the schedule in the
delivery table
, so restart the session first. If
/status
then names a different source than the one your administrator changed, a higher-priority source applies;
How Claude Code combines managed sources
gives the order.
​
A committed key doesn’t reach teammates
Two things keep a key in
.claude/settings.json
from applying for everyone who clones it:
Claude Code ignores the key in a repository file.
Look for
User, local, or managed
,
User or managed
,
User
,
Managed
, or
Global config
in the Scope column of the
settings index
. Those keys never apply from the shared file, apart from a few that a repository file can still switch off. Each of those entries says so on its Scope line.
Global config
keys apply only from
~/.claude.json
.
Inside the
env
key, the telemetry export variables never apply from the shared file either, apart from a few off values; see
Variables Claude Code ignores in
env
.
The key waits for trust.
permissions.allow
rules,
permissions.additionalDirectories
,
extraKnownMarketplaces
, and most
env
values apply only after each teammate
trusts the folder
. Until then they still see prompts and don’t get plugins from a marketplace the file declares.
deny
and
ask
rules apply right away.
​
Permission rules combine differently than you expected
You chose “Yes, and don’t ask again” on a permission prompt but still get prompted for the same tool.
That choice saved an
allow
rule to your local file, and an
allow
rule there doesn’t outrank an
ask
rule from a project or managed file;
how permission rules combine
explains the order. In the VS Code extension the approval card lets you pick the destination file, including the project’s shared file, which changes the rule for everyone; in the CLI, Claude Code writes only to your local file.
Your organization’s allow rules still apply alongside yours.
That’s expected: Claude Code merges
permissions.allow
across scopes, unless your organization sets
allowManagedPermissionRulesOnly
.
​
Exceptions to managed settings precedence
For a few keys whose values restrict a session, Claude Code honors a restrictive value from a scope that otherwise couldn’t override managed settings. Find the key in this table to see which value it honors and from where.
Key
Value Claude Code honors
Notes
disableClaudeAiConnectors
true
from any scope
Honored even when a managed source sets
false
enableArtifact
false
from any scope, and
disableArtifact: true
from any scope
Honored even when a managed source sets
true
; nothing turns the
Artifact tool
back on. Requires Claude Code v2.1.242 or later
isolatePeerMachines
true
from any scope
Honored even when a managed source sets
false
permissions.blockReadsOutsideWorkingDirectories
true
from any scope
Honored even when a managed source sets
false
. Requires Claude Code v2.1.257 or later
autoMode.classifyAllShell
true
from
~/.claude/settings.json
or
--settings
Honored even when a managed source sets
false
remoteControlAtStartup
false
from
.claude/settings.json
or
.claude/settings.local.json
Honored even when a managed source sets
true
; a project or local
true
is ignored
crossSessionInbound
A stricter value from
.claude/settings.json
or
.claude/settings.local.json
, on the
accept
<
hold
<
refuse
ladder
Honored over managed,
--settings
, and user values; a project or local value that isn’t stricter is ignored
useAutoModeDuringPlan
false
from any managed source,
--settings
,
~/.claude/settings.json
, or
.claude/settings.local.json
Honored even when the winning managed source sets
true
; a
false
in
.claude/settings.json
is ignored
syncClaudeAiSkills
false
from any managed source,
--settings
,
~/.claude/settings.json
, or
.claude/settings.local.json
Honored even when the winning managed source sets
true
; a
false
in
.claude/settings.json
is ignored
syncClaudeAiPlugins
false
from any managed source,
--settings
,
~/.claude/settings.json
, or
.claude/settings.local.json
Honored even when the winning managed source sets
true
; a
false
in
.claude/settings.json
is ignored
maxEffortLevel
A lower cap from any scope, including
--settings
Honored even when the managed settings Claude Code applies set a higher cap; the lowest cap applies. Requires Claude Code v2.1.267 or later
An app that runs Claude Code inside itself and sets
CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST
is also an exception. Claude Code takes that app’s model configuration over the
model
,
fallbackModel
,
modelPicker
, and
modelOverrides
keys from every managed source, and over the model-selection variables in a managed
env
block, such as
ANTHROPIC_MODEL
and the
ANTHROPIC_DEFAULT_*_MODEL
family. Claude Code keeps a managed
availableModels
allowlist in force unless the app supplies its own.
​
Settings in cloud sessions
A
cloud session
runs in a
cloud environment
on a fresh clone of your repository, not on your machine. That changes which settings reach it:
Cloud threads in a project
: in a cloud thread in a
project
, none of a repository’s
.claude/settings.json
permission rules, hooks, or
env
apply, however many repositories the project has.
What threads pick up from your repositories
lists what to use instead.
Shared project settings
(
.claude/settings.json
): read in a session with one repository outside a project’s threads, because the file is part of the clone and the session starts inside it. Commit a setting there to apply it in those sessions.
Shared project settings with several repositories
: in an Anthropic-hosted environment, a session with several repositories starts above the clones and reads only the
enabledPlugins
and
extraKnownMarketplaces
keys from each repository’s
.claude/settings.json
, not permission rules, hooks,
env
, or other keys. The marketplaces and plugins those two keys declare still
don’t load in a cloud session
. For a self-hosted environment, see
which repository’s settings apply
.
User and project local settings
(
~/.claude/settings.json
and
.claude/settings.local.json
): not read. Both stay on your machine, and the local file isn’t in the clone.
Managed settings
: a
managed-settings.json
file or MDM profile on your device doesn’t reach a cloud session. Your organization’s
server-managed settings
do;
surface coverage
lists which cloud sessions receive them. A
self-hosted environment
also reads the managed settings file in its runner image.
How Claude Code combines managed sources
says when that file applies.
/config
: in your browser at claude.ai/code, opens your claude.ai
Code
or
Claude Code
settings page instead of changing a value. To change a setting for a cloud session, set an
environment variable
on the environment. In a session with one repository outside a project’s threads, you can instead commit the key to that repository’s
.claude/settings.json
.
What carries over from your setup
lists the rest:
CLAUDE.md
, skills, MCP servers, plugins, and credentials.
​
What’s next
All settings
: every key, with where you set it and an example
Example settings files
: a personal file, a team file, and an organization’s managed file
Configure permissions
: allow, ask, and deny rules, and what Claude Code runs without asking
Environment variables
: the variables Claude Code reads and the
env
block
Debug your configuration
: when a setting doesn’t apply
Claude directory reference
: every file Claude Code reads, including subagents, MCP servers, plugins, and
CLAUDE.md
Was this page helpful?
Yes
No
{"docsConfig":{"theme":"mint","$schema":"https://mintlify.com/docs.json","name":"Claude Code Docs","description":"Official documentation for Claude Code, Anthropic's agentic coding tool available in the terminal, IDE, desktop app, and browser. Covers installation, configuration, skills, subagents, hooks, MCP, the Agent SDK, and reference material.","colors":{"primary":"#0E0E0E","light":"#D4A27F","dark":"#0E0E0E"},"logo":{"light":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/light.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=78fd01ff4f4340295a4f66e2ea54903c","dark":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/dark.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=1298a0c3b3a1da603b190d0de0e31712"},"favicon":"https://mintcdn.com/claude-code/T2WlxklWBkR5Y1mJ/favicon.ico?fit=max\u0026auto=format\u0026n=T2WlxklWBkR5Y1mJ\u0026q=85\u0026s=346a85952ae08d5ee90e3c34d4423930","appearance":{"default":"system"},"background":{"color":{"light":"#FDFDF7","dark":"#09090B"}},"navbar":{"links":[{"href":"https://platform.claude.com/","label":"Claude Developer Platform"}],"primary":{"type":"button","label":"Open Claude Code","href":"https://claude.ai/code"}},"footer":{"socials":{"x":"https://x.com/AnthropicAI","linkedin":"https://www.linkedin.com/company/anthropicresearch"},"links":[{"header":"Company","items":[{"label":"Anthropic","href":"https://www.anthropic.com/company"},{"label":"Careers","href":"https://www.anthropic.com/careers"},{"label":"Economic Futures","href":"https://www.anthropic.com/economic-futures"},{"label":"Research","href":"https://www.anthropic.com/research"},{"label":"News","href":"https://www.anthropic.com/news"},{"label":"Trust center","href":"https://trust.anthropic.com/"},{"label":"Transparency","href":"https://www.anthropic.com/transparency"}]},{"header":"Help and security","items":[{"label":"Availability","href":"https://www.anthropic.com/supported-countries"},{"label":"Status","href":"https://status.anthropic.com/"},{"label":"Support center","href":"https://support.claude.com/"}]},{"header":"Learn","items":[{"label":"Courses","href":"https://academy.claude.com/"},{"label":"MCP connectors","href":"https://claude.com/partners/mcp"},{"label":"Customer stories","href":"https://www.claude.com/customers"},{"label":"Engineering blog","href":"https://www.anthropic.com/engineering"},{"label":"Events","href":"https://www.anthropic.com/events"},{"label":"Powered by Claude","href":"https://claude.com/partners/powered-by-claude"},{"label":"Service partners","href":"https://claude.com/partners/services"},{"label":"Startups program","href":"https://claude.com/programs/startups"}]},{"header":"Terms and policies","items":[{"label":"Privacy choices","href":"https://www.anthropic.com/legal/privacy"},{"label":"Privacy policy","href":"https://www.anthropic.com/legal/privacy"},{"label":"Disclosure policy","href":"https://www.anthropic.com/responsible-disclosure-policy"},{"label":"Usage policy","href":"https://www.anthropic.com/legal/aup"},{"label":"Commercial terms","href":"https://www.anthropic.com/legal/commercial-terms"},{"label":"Consumer terms","href":"https://www.anthropic.com/legal/consumer-terms"}]}]},"seo":{"metatags":{"canonical":"https://code.claude.com/docs"}},"fonts":{"family":"Anthropic Sans"},"contextual":{"options":["copy","view","claude"],"display":"header"},"styling":{"latex":true},"navigation":{"languages":[{"language":"en","href":"en/overview"},{"language":"fr","href":"fr/overview"},{"language":"de","href":"de/overview"},{"language":"it","href":"it/overview"},{"language":"jp","href":"ja/overview"},{"language":"es","href":"es/overview"},{"language":"ko","href":"ko/overview"},{"language":"zh-CN","href":"zh-CN/overview"},{"language":"zh-TW","href":"zh-TW/overview"},{"language":"ru","href":"ru/overview"},{"language":"id","href":"id/overview"},{"language":"pt-BR","href":"pt/overview"}]}},"deployment":{"deploymentMetadataValue":{"subdomain":"claude-code","hasAudioNarration":false,"actualSubdomain":"claude-code","customDomains":["code.claude.com"],"gitSource":{"type":"github","owner":"anthropics","repo":"claude-code-docs","deployBranch":"main","contentDirectory":"","isPrivate":true,"mountPath":"","label":""},"chroma":{"liveDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85","collectionId":"5857522b-efb8-436a-af8d-9016a7b362b7","schemaVersion":"v3","latestBuiltDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85"},"feedback":{"thumbs":true},"entitlements":{"AI_CHAT":{"status":"ENABLED"},"REMOVE_BRANDING":{"status":"ENABLED"},"CONTEXTUAL_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"CODE_SNIPPET_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"WEB_MCP":{"status":"ENABLED"},"NARRATION":{"status":"ENABLED"}},"buildId":"6ae7a807e7a853c3110bf6c9","clientVersion":"0.0.4044","searchFilterCounts":[{"language":"en","tag":"Agent SDK","count":60},{"language":"en","tag":"Plugins","count":56},{"language":"de","tag":"Neuigkeiten","count":50},{"language":"en","tag":"What's New","count":50},{"language":"es","tag":"Novedades","count":50},{"language":"fr","tag":"Nouveautés","count":50},{"language":"it","tag":"Novità","count":50},{"language":"ko","tag":"새로운 기능","count":50},{"language":"pt-BR","tag":"Novidades","count":50},{"language":"ru","tag":"Что нового","count":50},{"language":"zh-TW","tag":"最新消息","count":50},{"language":"de","tag":"Erste Schritte","count":49},{"language":"es","tag":"Primeros pasos","count":49},{"language":"fr","tag":"Premiers pas","count":49},{"language":"id","tag":"Memulai","count":49},{"language":"it","tag":"Per iniziare","count":49},{"language":"jp","tag":"はじめに","count":49},{"language":"ko","tag":"시작하기","count":49},{"language":"pt-BR","tag":"Primeiros passos","count":49},{"language":"ru","tag":"Начало работы","count":49},{"language":"zh-TW","tag":"快速入門","count":49},{"language":"en","tag":"Getting started","count":48},{"language":"zh-CN","tag":"快速入门","count":46},{"language":"en","tag":"Overview","count":41},{"language":"de","tag":"Agent SDK","count":36},{"language":"en","tag":"Setup and access","count":36},{"language":"es","tag":"Agent SDK","count":36},{"language":"id","tag":"Agent SDK","count":36},{"language":"it","tag":"Agent SDK","count":36},{"language":"jp","tag":"Agent SDK","count":36},{"language":"pt-BR","tag":"Agent SDK","count":36},{"language":"ru","tag":"Agent SDK","count":36},{"language":"zh-CN","tag":"Agent SDK","count":36},{"language":"zh-TW","tag":"Agent SDK","count":36},{"language":"de","tag":"Administration","count":34},{"language":"en","tag":"Administration","count":34},{"language":"es","tag":"Administración","count":34},{"language":"fr","tag":"Administration","count":34},{"language":"id","tag":"Administrasi","count":34},{"language":"it","tag":"Amministrazione","count":34},{"language":"jp","tag":"管理","count":34},{"language":"ko","tag":"관리","count":34},{"language":"pt-BR","tag":"Administração","count":34},{"language":"ru","tag":"Администрирование","count":34},{"language":"zh-CN","tag":"管理","count":34},{"language":"zh-TW","tag":"管理","count":34},{"language":"de","tag":"Plugins","count":32},{"language":"es","tag":"Plugins","count":32},{"language":"fr","tag":"SDK Agent","count":32},{"language":"fr","tag":"Plugins","count":32},{"language":"id","tag":"Plugin","count":32},{"language":"it","tag":"Plugin","count":32},{"language":"jp","tag":"プラグイン","count":32},{"language":"ko","tag":"Agent SDK","count":32},{"language":"ko","tag":"플러그인","count":32},{"language":"pt-BR","tag":"Plugins","count":32},{"language":"ru","tag":"Плагины","count":32},{"language":"zh-CN","tag":"插件","count":32},{"language":"zh-TW","tag":"外掛","count":32},{"language":"en","tag":"Reference","count":28},{"language":"es","tag":"Configuración","count":28},{"language":"jp","tag":"設定","count":28},{"language":"zh-TW","tag":"設定","count":28},{"language":"de","tag":"Konfiguration","count":25},{"language":"en","tag":"Configuration","count":25},{"language":"fr","tag":"Configuration","count":25},{"language":"id","tag":"Konfigurasi","count":25},{"language":"id","tag":"Apa yang Baru","count":25},{"language":"id","tag":"Yang Baru","count":25},{"language":"it","tag":"Configurazione","count":25},{"language":"jp","tag":"新機能","count":25},{"language":"jp","tag":"最新情報","count":25},{"language":"ko","tag":"구성","count":25},{"language":"pt-BR","tag":"Configuração","count":25},{"language":"ru","tag":"Конфигурация","count":25},{"language":"zh-CN","tag":"配置","count":25},{"language":"zh-CN","tag":"新功能","count":25},{"language":"zh-CN","tag":"最新动态","count":25},{"language":"en","tag":"Settings","count":24},{"language":"de","tag":"Mit Claude Code entwickeln","count":22},{"language":"es","tag":"Crea con Claude Code","count":22},{"language":"fr","tag":"Développer avec Claude Code","count":22},{"language":"id","tag":"Membangun dengan Claude Code","count":22},{"language":"it","tag":"Crea con Claude Code","count":22},{"language":"jp","tag":"Claude Code で構築","count":22},{"language":"ko","tag":"Claude Code로 만들기","count":22},{"language":"pt-BR","tag":"Desenvolva com Claude Code","count":22},{"language":"ru","tag":"Разработка с Claude Code","count":22},{"language":"zh-CN","tag":"使用 Claude Code 构建","count":22},{"language":"zh-TW","tag":"使用 Claude Code 打造","count":22},{"language":"de","tag":"Referenz","count":20},{"language":"es","tag":"Referencia","count":20},{"language":"fr","tag":"Référence","count":20},{"language":"id","tag":"Referensi","count":20},{"language":"it","tag":"Riferimento","count":20},{"language":"jp","tag":"リファレンス","count":20},{"language":"ko","tag":"레퍼런스","count":20},{"language":"pt-BR","tag":"Referência","count":20},{"language":"ru","tag":"Справочник","count":20},{"language":"zh-CN","tag":"参考","count":20},{"language":"de","tag":"Plattformen und Integrationen","count":19},{"language":"es","tag":"Plataformas e integraciones","count":19},{"language":"fr","tag":"Plateformes et intégrations","count":19},{"language":"id","tag":"Platform dan integrasi","count":19},{"language":"it","tag":"Piattaforme e integrazioni","count":19},{"language":"jp","tag":"プラットフォームと連携","count":19},{"language":"ko","tag":"플랫폼 및 통합","count":19},{"language":"pt-BR","tag":"Plataformas e integrações","count":19},{"language":"ru","tag":"Платформы и интеграции","count":19},{"language":"zh-CN","tag":"平台与集成","count":19},{"language":"zh-TW","tag":"平台與整合","count":19},{"language":"de","tag":"Code-Review und Pull Requests","count":14},{"language":"es","tag":"Revisión de código y pull requests","count":14},{"language":"fr","tag":"Revue de code et pull requests","count":14},{"language":"it","tag":"Code review e pull request","count":14},{"language":"ko","tag":"코드 리뷰 및 풀 리퀘스트","count":14},{"language":"pt-BR","tag":"Revisão de código e pull requests","count":14},{"language":"ru","tag":"Код-ревью и pull request","count":14},{"language":"zh-TW","tag":"程式碼審查與 pull request","count":14},{"language":"zh-TW","tag":"部署","count":11}]},"assistantConfig":{"enableAskAiButton":false,"enableStarterQuestions":false,"enableAskAiSearchBar":true},"basePath":"/docs","hasChatPermissions":true,"hasWebMcpPermissions":true,"toggles":[{"name":"kill-isr","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"assistant-bash","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"chat-bucketing-batched","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"agent-mintlify-slack","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"agent-integrations-settings","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automations-pr-grouping","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"custom-prefix","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"analytics-v7","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"user-flows-analytics","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"no-publish-flow","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-onboarding","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"llms-txt-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"snapshot-serving-live","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"stripTemperatureMiddleware","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"support-platform-pylon-zendesk","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"snapshot-serving","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"instant-rollback","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"granular-notifications-server","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"granular-notifications","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automations-fable","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"fixed-ai-action-pricing","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automation-resolve-merge-conflict","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"scoped-publishing","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"mintql","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"page-level-analytics","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"editor-version-history-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"billing-page-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"full-page-search","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workspace-projects","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"assistant-v5","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"byok-sep-25","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"fork-pr-previews","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"revalidation-jwt","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"vite-origin","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"billing-updated-9-15","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":t

## Source (subagents): https://docs.claude.com/en/docs/claude-code/sub-agents

Create custom subagents - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
Subagents are specialized AI assistants that handle specific types of tasks. Use one when a side task would flood your main conversation with search results, logs, or file contents you won’t reference again: the subagent does that work in its own context and returns only the summary. Define a custom subagent when you keep spawning the same kind of worker with the same instructions.
Each subagent runs in its own context window with a custom system prompt, specific tool access, and independent permissions. It also sends its own requests, which count toward the same
usage limits
as your main conversation. When Claude encounters a task that matches a subagent’s description, it delegates to that subagent, which works independently and returns results. To see the context savings in practice, the
context window visualization
walks through a session where a subagent handles research in its own separate window.
Subagents work within a single session. To run many independent sessions in parallel and monitor them from one place, see
background agents
. For separate sessions that pass messages to each other, see
cross-session messaging
. For a coordinated team of sessions Claude spawns and supervises, see
agent teams
.
Subagents help you:
Preserve context
by keeping exploration and implementation out of your main conversation
Enforce constraints
by limiting which tools a subagent can use
Reuse configurations
across projects with user-level subagents
Specialize behavior
with focused system prompts for specific domains
Control costs
by routing tasks to faster, lower-cost models like Haiku
Claude uses each subagent’s description to decide when to delegate tasks. When you create a subagent, write a clear description so Claude knows when to use it.
Those descriptions take up context, so keep them short. When the combined descriptions of your subagents, except the built-in ones, exceed 15,000 tokens, Claude Code shows a
warning at startup with the total token count
. Trim the
description
fields of your subagents, and move detail into each subagent’s system prompt, which only loads when that subagent runs.
​
Built-in subagents
Claude Code includes built-in subagents that Claude automatically uses when appropriate. Each inherits the parent conversation’s permission rules; most run with a restricted tool set.
Explore and Plan start without your CLAUDE.md files and the git status snapshot to keep research fast and inexpensive. Other built-in and
custom subagents
load both, unless you set
omitClaudeMd
in a custom subagent’s definition to start it without the user, project, and local CLAUDE.md files. For the full breakdown of what reaches a subagent, see
what loads at startup
.
Explore
Plan
General-purpose
Other
A fast, read-only agent optimized for searching and analyzing codebases.
Model
: the main conversation’s model. When the main conversation runs Fable, Explore’s model depends on how you connect:
With a Claude subscription, an Anthropic Console account, or an
LLM gateway
reached through
ANTHROPIC_BASE_URL
, Explore runs on the Opus model that the
opus
alias
resolves to.
On Amazon Bedrock, Google Cloud’s Agent Platform, Microsoft Foundry,
Claude Platform on AWS
, or a
Claude apps gateway
, Explore stays on the main conversation’s model.
Tools
: read-only tools; Write and Edit are denied
Purpose
: file discovery, code search, codebase exploration
A
user or project subagent
named
Explore
overrides the built-in and keeps its own
model
field, so define one with
model: haiku
to run exploration on a lower-cost model. To force one model onto every subagent, Explore included, see
Run every subagent on one model
.
Claude delegates to Explore when it needs to search or understand a codebase without making changes. This keeps exploration results out of your main conversation context.
When invoking Explore, Claude specifies a thoroughness level:
quick
for targeted lookups,
medium
for balanced exploration, or
very thorough
for comprehensive analysis.
A research agent used during
plan mode
to gather context before presenting a plan.
Model
: inherits from the main conversation, unless you set
CLAUDE_CODE_SUBAGENT_MODEL
and
force it onto every subagent
Tools
: read-only tools; Write and Edit are denied
Purpose
: codebase research for planning
When you’re in plan mode and Claude needs to understand your codebase, it delegates research to the Plan subagent so that exploration output stays in a separate context window while the main conversation remains read-only.
A capable agent for complex, multi-step tasks that require both exploration and action.
Model
: the
CLAUDE_CODE_SUBAGENT_MODEL
model if you set one and nothing assigns a model another way, otherwise the main conversation’s model;
Choose a model
states the full order, and
Run every subagent on one model
shows how to make the variable override those sources
Tools
: every tool
available to subagents
Purpose
: complex research, multi-step operations, code modifications
Claude delegates to general-purpose when the task requires both exploration and modification, complex reasoning to interpret results, or multiple dependent steps.
Claude Code includes additional helper agents for specific tasks. These are typically invoked automatically, so you don’t need to use them directly.
Agent
Model
When Claude uses it
claude
None of its own; follows the
model order
when Claude spawns it as a subagent
When a task doesn’t fit a more specialized agent. A catch-all with every tool
available to subagents
. Also the default agent for a dispatched
background session
;
which permission mode it starts in
depends on how the session was started
statusline-setup
Sonnet
When you run
/statusline
to configure your status line
claude-code-guide
Haiku
When you ask questions about Claude Code features
Built-in subagents are registered by default in interactive sessions. To restrict them:
To block a specific built-in type, add it to
permissions.deny
as shown in
Disable specific subagents
.
To prevent Claude from delegating to any subagent, deny the
Agent
tool itself with
permissions.deny
.
To remove only the built-in
Explore
and
Plan
subagents, set
CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS=1
. Claude reads and explores files directly instead of delegating to them. Requires Claude Code v2.1.198 or later.
In
non-interactive mode
and the
Agent SDK
, set
CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1
to remove all built-in types and supply only your own.
An Agent tool call that omits
subagent_type
fails with
subagent_type is required
when the session has no
general-purpose
subagent to fall back on.
Beyond these built-in subagents, you can create your own with custom prompts, tool restrictions, permission modes, hooks, and skills. The following sections show how to get started and customize subagents.
​
Quickstart: create your first subagent
Subagents are Markdown files with YAML frontmatter. To create one, ask Claude to write it for you, or
write the file yourself
.
This walkthrough creates a user-level subagent that reviews code and suggests improvements.
1
Ask Claude to create the subagent
In Claude Code, describe the subagent you want and where to save it:
Create a personal code-improver subagent in ~/.claude/agents/ that scans
files and suggests improvements for readability, performance, and best
practices. It should explain each issue, show the current code, and
provide an improved version. Make it read-only and have it use Sonnet.
Claude writes the file with a
name
, a
description
, a
tools
list, a
model
, and a system prompt.
2
Review the file
Open
~/.claude/agents/code-improver.md
and confirm the frontmatter matches what you asked for. The result looks like this:
---
name
:
code-improver
description
:
Scans files and suggests improvements for readability, performance, and best practices. Use after writing or modifying code.
tools
:
Read, Grep, Glob
model
:
sonnet
---
You are a code improvement specialist. For each issue you find, explain
the problem, show the current code, and provide an improved version.
Because the file lives in
~/.claude/agents/
, the subagent is available in every project on your machine. To scope it to one project instead, move it to that project’s
.claude/agents/
directory.
Choose the subagent scope
compares the two.
3
Try it out
Ask Claude to delegate to the new subagent:
Use the code-improver agent to suggest improvements in this project
Claude delegates to your new subagent, which scans the codebase and returns improvement suggestions. In the transcript, the delegation appears as a tool call row showing the subagent’s name followed by a short task description, such as
code-improver(Suggest code improvements)
.
If Claude can’t find the new subagent, restart Claude Code and try again. This happens only when
~/.claude/agents/
didn’t exist before the session started, because a running session doesn’t detect a newly created
agents
directory.
You now have a subagent you can use in any project on your machine to analyze codebases and suggest improvements.
You can also write subagent files by hand, define them via CLI flags, or distribute them through plugins. The following sections cover all configuration options.
Running
/agents
prints a reminder to ask Claude or edit
.claude/agents/
and
~/.claude/agents/
directly.
On Claude Code v2.1.197 and earlier,
/agents
opens an interactive wizard with a
Running
tab that lists live subagents and a
Library
tab for creating, editing, and deleting them.
​
Configure subagents
A subagent’s file location determines who it’s available to, and its frontmatter determines what it can do. This section covers where subagent files live and every field they support.
​
Choose the subagent scope
Store subagent files in different locations depending on scope. When multiple subagents share the same name, Claude Code uses the one from the higher-priority location.
Location
Scope
Priority
How to create
Managed settings
Organization-wide
1 (highest)
Deployed via
managed settings
--agents
CLI flag
Current session
2
Pass JSON when launching Claude Code
.claude/agents/
Current project
3
Ask Claude, or create the file manually
~/.claude/agents/
All your projects
4
Ask Claude, or create the file manually
Plugin’s
agents/
directory
Where plugin is enabled
5 (lowest)
Installed with
plugins
Project subagents
(
.claude/agents/
) are ideal for subagents specific to a codebase. Check them into version control so your team can use and improve them collaboratively.
Project subagents are discovered by walking up from the current working directory, so every
.claude/agents/
between there and the repository root is scanned. When more than one of these nested directories defines the same
name
, Claude Code uses the definition closest to the working directory.
When you add a directory with
--add-dir
or
/add-dir
, Claude Code also loads its
.claude/agents/
folder, alongside your project subagents. See
Additional directories
for which other configuration types load from
--add-dir
. To share subagents across projects without
--add-dir
, use
~/.claude/agents/
or a
plugin
.
User subagents
(
~/.claude/agents/
) are personal subagents available in all your projects.
Claude Code scans
.claude/agents/
and
~/.claude/agents/
recursively, so you can organize definitions into subfolders such as
agents/review/
or
agents/research/
. The subdirectory path doesn’t affect how a subagent is identified or invoked, because identity comes only from the
name
frontmatter field.
Keep
name
values unique across the whole tree: if two files under the same
.claude/agents/
directory, including its subfolders, declare the same name, Claude Code loads only one of them, chosen by filesystem read order rather than a documented precedence. Across nested project directories, the definition closest to the working directory wins, as described above. The
/doctor
setup checkup reports files in the same directory that share a name and proposes renaming or removing all but one.
Plugin
agents/
directories are also scanned recursively. Unlike project and user scopes, a subfolder inside a plugin’s
agents/
directory becomes part of the
scoped identifier
: a file at
agents/review/security.md
in plugin
my-plugin
registers as
my-plugin:review:security
.
CLI-defined subagents
are passed as JSON when launching Claude Code. They exist only for that session and aren’t saved to disk, making them useful for quick testing or automation scripts. You can define multiple subagents in a single
--agents
call:
macOS, Linux, WSL
Windows PowerShell
claude
--agents
'{
"code-reviewer": {
"description": "Expert code reviewer. Use proactively after code changes.",
"prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
"tools": ["Read", "Grep", "Glob", "Bash"],
"model": "sonnet"
},
"debugger": {
"description": "Debugging specialist for errors and test failures.",
"prompt": "You are an expert debugger. Analyze errors, identify root causes, and provide fixes."
}
}'
claude
--
agents
@'
{
"code-reviewer": {
"description": "Expert code reviewer. Use proactively after code changes.",
"prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
"tools": ["Read", "Grep", "Glob", "Bash"],
"model": "sonnet"
},
"debugger": {
"description": "Debugging specialist for errors and test failures.",
"prompt": "You are an expert debugger. Analyze errors, identify root causes, and provide fixes."
}
}
'@
In
non-interactive mode
,
--agents
also accepts the path to a JSON file holding the same object, for definitions too large to pass on the command line. For example,
claude -p --agents ./agents.json "Review my changes"
reads the definitions from that file. In an interactive session, Claude Code refuses a file path. The file form requires Claude Code v2.1.281 or later.
Each top-level key in the JSON is an agent’s name, and its value is that agent’s definition. Don’t start a name with
-
. A definition takes these fields:
prompt
: the agent’s system prompt, equivalent to the markdown body in file-based subagents.
prompt
may be empty. If you select an agent with an empty
prompt
and no
memory
field as the session’s agent with
--agent
, the session’s system prompt is left unchanged. An empty
prompt
requires Claude Code v2.1.281 or later.
Frontmatter fields
:
description
,
tools
,
disallowedTools
,
model
,
permissionMode
,
mcpServers
,
hooks
,
maxTurns
,
autoCompactWindow
,
skills
,
initialPrompt
,
memory
,
effort
,
background
,
omitClaudeMd
, and
isolation
.
Ignored fields
:
color
and
experimental
aren’t accepted here and are ignored rather than rejected.
For what Claude Code does with a value it can’t load, and the flags and environment variable that skip that check, see
Invalid --agents configuration
.
Managed subagents
are deployed by organization administrators. Place markdown files in
.claude/agents/
inside the
managed settings directory
, using the same frontmatter format as project and user subagents. Managed definitions take precedence over project and user subagents with the same name.
Plugin subagents
come from
plugins
you’ve installed. They load automatically alongside your custom subagents and appear in the @-mention typeahead under their scoped name. See the
plugin components reference
for details on creating plugin subagents.
For security reasons, plugin subagents don’t support the
hooks
,
mcpServers
, or
permissionMode
frontmatter fields. These fields are ignored when loading agents from a plugin. If you need them, copy the agent file into
.claude/agents/
or
~/.claude/agents/
. You can also add rules to
permissions.allow
in
settings.json
or
settings.local.json
, but these rules apply to the entire session, not only the plugin subagent.
If you’re the plugin’s author, ship the hooks in the plugin’s
hooks/hooks.json
and the MCP servers in its
.mcp.json
instead. They apply whenever the plugin is enabled rather than only inside the subagent.
You can also reuse a subagent definition as an
agent team
teammate: name the subagent type when you ask Claude to spawn the teammate, and Claude Code applies parts of that definition to it.
Use subagent definitions for teammates
says which scopes and which parts apply in each display mode.
​
Write subagent files
Subagent files use YAML frontmatter for configuration, followed by the system prompt in Markdown:
Claude Code watches
~/.claude/agents/
and
.claude/agents/
. When you add or edit a subagent file on disk, or ask Claude to write one for you, Claude Code detects the change within a few seconds and the next delegation uses the updated definition, with no restart needed.
Three cases still need a restart:
The watcher covers only directories that existed when the session started, so after creating a scope’s first agent file in a new
agents
directory, restart to load it.
Claude Code doesn’t watch
.claude/agents/
inside directories added with
--add-dir
or
/add-dir
, so after adding or editing a subagent there, restart to load the change.
Sessions started with
--disable-slash-commands
don’t watch these directories at all.
.claude/agents/code-reviewer.md
---
name
:
code-reviewer
description
:
Reviews code for quality and best practices
tools
:
Read, Glob, Grep
model
:
sonnet
---
You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.
The frontmatter defines the subagent’s metadata and configuration. The body becomes the system prompt that guides the subagent’s behavior. Subagents receive only this system prompt plus basic environment details like the working directory, not the Claude Code system prompt.
In
non-interactive mode
, pass
--append-subagent-system-prompt
to append your text to the end of every subagent’s system prompt, nested subagents included, apart from a
forked subagent
, which reuses the conversation’s own prompt. Requires Claude Code v2.1.205 or later. If your text is too long to pass on the command line, save it to a file and pass the path with
--append-subagent-system-prompt-file
instead. The file flag requires Claude Code v2.1.261 or later.
A subagent starts in the main conversation’s current working directory. Within a subagent,
cd
commands don’t persist between Bash or PowerShell tool calls and don’t affect the main conversation’s working directory. To give the subagent an isolated copy of the repository instead, set
isolation: worktree
.
A subagent with
isolation: worktree
runs its Bash and PowerShell commands inside its worktree. A command whose working directory resolves to your main checkout instead, for example because the worktree directory was removed while the subagent was running, fails with an error.
This working-directory check covers the whole repository containing the directory you launched Claude Code from. When your session runs in a linked
worktree
of its own, the check also covers the main checkout that worktree is linked from.
For Bash commands, Claude Code also checks the command itself in two ways:
It blocks a command that redirects git into the main checkout.
It refuses a command when it can’t verify from the command text that any git the command runs stays inside the worktree, for example when the command name is computed at runtime.
The redirect vectors and the shape rules are listed under
How Claude Code enforces isolation
. PowerShell commands get only the working-directory check.
Monitor
commands go through the same working-directory and command-content checks as Bash commands.
When the main conversation itself runs isolated in a worktree, Claude Code applies the same checks to the session and to every subagent it spawns, including subagents without
isolation: worktree
; see
How Claude Code enforces isolation
.
​
Frontmatter reference
Configure a subagent with YAML
frontmatter
between
---
markers at the top of its file, and write its system prompt as Markdown after the closing
---
. Only
name
and
description
are required.
Multi-word field names use camelCase, such as
maxTurns
and
disallowedTools
, and must match the table exactly: Claude Code ignores a field it doesn’t recognize without reporting an error.
To find a misspelled field in a subagent that loaded, run
claude --debug
in your shell and search the debug log at
~/.claude/debug/<session-id>.txt
for
does not recognize or apply
. The debug log names up to five top-level fields in the subagent’s file that Claude Code doesn’t recognize, with the likely intended name when a supported field is close. Requires Claude Code v2.1.296 or later.
To find out why a subagent file didn’t load, see
Subagent files Claude Code skips
.
Field
Required
Description
name
Yes
Unique identifier of at most 256 characters, such as
code-reviewer
or
reviewer-v2
.
Hooks
receive this value as
agent_type
. The filename doesn’t have to match. Names can’t contain
:
, which is reserved for
plugin-scoped identifiers
such as
my-plugin:reviewer
description
Yes
When Claude should delegate to this subagent
tools
No
Tools
the subagent can use, as a comma-separated string such as
Read, Grep, Bash
or a YAML list. Inherits every tool available to subagents if omitted. If no entry in the list resolves to a tool, the subagent usually
fails to launch
with an error naming the entries. To preload Skills into context, use the
skills
field rather than listing
Skill
here
disallowedTools
No
Tools to deny, removed from inherited or specified list. Same format as
tools
. An entry with a specifier, such as
Bash(git push *)
, still
removes the whole tool
model
No
Model
to use:
sonnet
,
opus
,
haiku
,
fable
, a full model ID such as
claude-opus-5-5
, or
inherit
. When you omit it, Claude Code picks the model in the
subagent model order
permissionMode
No
Permission mode
:
default
,
acceptEdits
,
auto
,
dontAsk
,
bypassPermissions
,
plan
, or
manual
as an alias for
default
. Ignored for
plugin subagents
maxTurns
No
Maximum number of agentic turns before the subagent stops. When the subagent reaches the limit, Claude Code returns its output marked as partial, and Claude can
resume it
to continue. The partial marking requires Claude Code v2.1.246 or later
autoCompactWindow
No
Lower the
auto-compact window
for this subagent to a token count from
100000
to
1000000
. Requires Claude Code v2.1.296 or later
skills
No
Skills
to preload into the subagent’s context at startup. The full skill content is injected, not only the description. Subagents can still invoke unlisted project, user, and plugin skills through the Skill tool
mcpServers
No
MCP servers
available to this subagent. Each entry is either a server name referencing an already-configured server (e.g.,
"slack"
) or an inline definition with the server name as key and a full
MCP server config
as value. Ignored for
plugin subagents
hooks
No
Lifecycle hooks
scoped to this subagent. Ignored for
plugin subagents
memory
No
Persistent memory scope
:
user
,
project
, or
local
. Enables cross-session learning
background
No
Set to
true
to keep this subagent in the background even when Claude asks to wait for it. By default, subagents Claude spawns from the main conversation already
start in the background
omitClaudeMd
No
Set to
true
to start this subagent without the user, project, and local CLAUDE.md files in its
initial context
;
managed policy files
still load, except for
managed subagents
. Use it for subagents that take everything they need from the delegation prompt. Ignored when the agent runs as the main session agent via
--agent
or the
agent
setting. Requires Claude Code v2.1.271 or later
effort
No
Effort level when this subagent is active. Overrides the session effort level, but not the
CLAUDE_CODE_EFFORT_LEVEL
environment variable. Options:
low
,
medium
,
high
,
xhigh
,
max
; available levels depend on the model. See
Choose an effort level
isolation
No
Set to
worktree
to run the subagent in a temporary
git worktree
, giving it an isolated copy of the repository branched by default from your
default branch
rather than the parent session’s
HEAD
. The worktree is automatically cleaned up if the subagent makes no changes
color
No
Display color for the subagent in the task list and transcript. Accepts
red
,
blue
,
green
,
yellow
,
purple
,
orange
,
pink
, or
cyan
initialPrompt
No
Auto-submitted as the first user turn when this agent runs as the main session agent (via
--agent
or the
agent
setting).
Commands
and
skills
are processed. Prepended to any user-provided prompt. Ignored for
plugin subagents
experimental
No
Map of experimental options. Set its
cacheTtl
key to
5m
or
1h
to choose the
prompt cache lifetime
for this subagent’s requests, at the frontmatter’s place in the
cache lifetime precedence
. Claude Code ignores any other value, ignores
1h
while your Claude subscription is using usage credits, and reads the field only from subagent files. Requires Claude Code v2.1.248 or later
Write
cacheTtl
inside the
experimental
map, not at the top level of the frontmatter.
---
name
:
repo-auditor
description
:
Audits a large repository and reports what it finds
experimental
:
cacheTtl
:
1h
---
​
Subagent files Claude Code skips
Claude Code skips a file in a project, user, or managed
agents
directory, or in one under a directory you add with
--add-dir
, without reporting it in the session, when the frontmatter has any of these problems:
No
name
: Claude Code treats the file as documentation kept beside your agents.
An opening
---
that isn’t the file’s first line
: Claude Code reads the file as having no frontmatter and treats it as documentation.
A
name
that starts with
-
, contains
:
, or is longer than 256 characters
: Claude Code skips the file and writes an error to the debug log.
A
name
but no
description
: Claude Code skips the file and writes the reason to the debug log.
YAML that doesn’t parse
: Claude Code reads no fields from the file, skips it, and writes the parse error to the debug log.
To see the debug log, run Claude Code with
--debug
.
A
plugin subagent
whose frontmatter has no
name
or doesn’t parse still loads, under its filename.
Check an
agents
directory before a session
To find files in an
agents
directory whose frontmatter doesn’t parse, run
claude plugin validate
against the directory, for example
.claude/agents
or
~/.claude/agents
. Claude Code checks only
the directory you name
, and doesn’t flag a file whose frontmatter parses but has no
name
. Requires Claude Code v2.1.233 or later.
​
Choose a model
The
model
field controls which model the subagent uses:
Model alias
: use one of the available aliases:
sonnet
,
opus
,
haiku
, or
fable
Full model ID
: use a full model ID such as
claude-opus-5-5
or
claude-sonnet-5
. Accepts the same values as the
--model
flag
inherit
: use the same model as the main conversation
When Claude invokes a subagent, it can also pass a
model
parameter for that specific invocation. On an Agent tool call, that parameter takes a model alias:
sonnet
,
opus
,
haiku
, or
fable
. Claude can’t pass a full model ID or
inherit
on that call. Claude Code resolves the subagent’s model in this order:
The per-invocation
model
parameter
The subagent definition’s
model
frontmatter, where
inherit
selects the main conversation’s model
The
CLAUDE_CODE_SUBAGENT_MODEL
environment variable, when you set it to a model alias or model ID
The main conversation’s model
If an installed
mod
sets a model in its
agent.spawn
hook, Claude Code uses that model in place of the per-invocation parameter.
In two cases, a family alias such as
opus
in the per-invocation parameter or the frontmatter resolves to the main conversation’s model instead of the
version the alias points to
:
The main conversation’s model belongs to that family
: the subagent runs on the main conversation’s exact model, including any
[1m]
suffix, so it gets the same
extended context
window as the main conversation.
Claude Code can’t tell the main conversation’s model family, on
a provider other than the Anthropic API
: this can happen with an
application inference profile ARN
on Amazon Bedrock that Claude Code hasn’t resolved to a backing model. This case covers only the
opus
alias, and doesn’t apply when you set
ANTHROPIC_DEFAULT_OPUS_MODEL
, since
opus
then resolves to the model you set.
An alias in
CLAUDE_CODE_SUBAGENT_MODEL
always resolves to the version the alias points to, even when it names the main conversation’s family. Setting the variable to
inherit
is the same as leaving it unset.
Setting
CLAUDE_CODE_SUBAGENT_MODEL
by itself doesn’t change the model the built-in Explore and Plan subagents run on. To change it, see
Run every subagent on one model
.
Before v2.1.251,
CLAUDE_CODE_SUBAGENT_MODEL
came first in this order and overrode both the per-invocation parameter and the frontmatter, including
model: inherit
.
Claude Code checks the per-invocation parameter, frontmatter, and environment variable values against your organization’s
availableModels
allowlist. For a blocked value, it substitutes another model:
When the blocked value is a family alias such as
opus
, Claude Code runs the subagent on the newest version of that family the allowlist permits, following the same
substitution rules and provider scope
as
/model
. Before v2.1.222, Claude Code ran the subagent on the inherited model for a blocked family alias as well.
For any other blocked value, on providers where that substitution doesn’t operate, or when the allowlist permits no version of the family, Claude Code runs the subagent on the inherited model instead. If you set
CLAUDE_CODE_SUBAGENT_MODEL
, Claude Code tries that model first, under these same rules.
In interactive sessions, Claude Code shows a warning naming the requested model and the model the subagent runs on, for either substitution.
To check which model a subagent is running on, run
/tasks
. Claude Code names the model on the subagent’s row, and adds the
effort level
set for that subagent, if any. Requires Claude Code v2.1.242 or later.
A per-invocation
model
parameter also applies when the subagent is
resumed or sent a follow-up message
, so the subagent stays on that model.
As of v2.1.198, subagents also inherit the main conversation’s
extended thinking
configuration: if thinking is on in your session, it’s on for the subagent, and if it’s off, it stays off. There is no per-subagent thinking setting. Before v2.1.198, subagents ran with extended thinking disabled regardless of the main conversation’s setting.
​
Run every subagent on one model
CLAUDE_CODE_SUBAGENT_MODEL
is a default, so a subagent’s definition or a model Claude passes still takes precedence over it. To apply one model to every subagent,
teammate
, and
workflow agent
, also set
CLAUDE_CODE_SUBAGENT_MODEL_FORCE
to
1
. Requires Claude Code v2.1.257 or later.
If you set both variables, subagents run on the model in
CLAUDE_CODE_SUBAGENT_MODEL
.
If you set only
CLAUDE_CODE_SUBAGENT_MODEL_FORCE
, subagents run on the main conversation’s model, except that the built-in Explore subagent runs on the
model listed for it under Built-in subagents
.
For example, to run every subagent on Haiku, set both variables in the
env
block of a
settings file
:
{
"env"
: {
"CLAUDE_CODE_SUBAGENT_MODEL"
:
"haiku"
,
"CLAUDE_CODE_SUBAGENT_MODEL_FORCE"
:
"1"
}
}
To check that the setting took effect, run
/tasks
while a subagent is running. The subagent’s row shows the model it runs on.
While
CLAUDE_CODE_SUBAGENT_MODEL_FORCE
is
on
, Claude Code ignores the
model
field in subagent definitions, and Claude can’t pass a model when it starts a subagent. These subagents still run on the main conversation’s model:
A
fork
A
skill that runs in a subagent
with
model: inherit
​
Choose an effort level
To run a subagent at its own
effort level
, set the
effort
field in its definition.
When you ask Claude to run a non-fork subagent at a specific effort level, it can also pass an
effort
parameter for that invocation. The parameter overrides the
effort
field and stays in effect when the subagent is
resumed
. The
CLAUDE_CODE_EFFORT_LEVEL
environment variable takes precedence over both. The per-invocation parameter requires Claude Code v2.1.292 or later.
​
Control subagent capabilities
You can control what subagents can do through tool access, permission modes, and conditional rules.
​
Available tools
Subagents inherit the
built-in tools
and MCP tools available in the main conversation, narrowed by two filters: the first removes a short list of tools from every subagent, and the second reduces the built-in tool set for subagents that run in the
background
, which is the default. On macOS, Linux, and WSL, a subagent can also receive the Glob and Grep tools when the main conversation doesn’t have them, as described under
Glob tool behavior
.
Forks
skip both filters and receive the main conversation’s exact tool pool. The first filter removes these tools, even when listed in the
tools
field:
Agent
, when the subagent is at the
depth limit
; in a
fork
the tool stays listed but returns an error instead of spawning
AskUserQuestion
EndConversation
, which can end only the main conversation; see
EndConversation tool behavior
EnterPlanMode
ExitPlanMode
, unless the subagent’s
permissionMode
is
plan
ScheduleWakeup
WaitForMcpServers
Workflow
The second filter applies to subagents running in the background. Apart from
Agent
and
ExitPlanMode
, which follow the first filter’s conditions wherever the subagent runs, a background subagent keeps every MCP tool but only these built-in tools:
Read
,
Grep
,
Glob
,
LSP
,
Bash
,
PowerShell
,
Edit
,
Write
,
NotebookEdit
,
WebFetch
,
WebSearch
,
TodoWrite
,
Skill
,
ToolSearch
,
EnterWorktree
,
ExitWorktree
,
Monitor
,
TaskStop
,
SendMessage
, and
Artifact
, plus
SubagentHandback
for a subagent that reports through it. Claude Code removes every other built-in tool from a background subagent, whether inherited or listed in the
tools
field, so the same definition can resolve to different tools in the foreground and the background. The removal reports no error unless it leaves the
tools
list
resolving to nothing
.
Before v2.1.280, background subagents couldn’t use
LSP
.
ListAgents
follows these filters like any built-in tool: a foreground subagent inherits it in sessions where cross-session messaging is enabled, and a background subagent doesn’t keep it.
Teammates in
agent teams
additionally keep the task tools and cron tools:
TaskCreate
,
TaskGet
,
TaskList
,
TaskUpdate
,
CronCreate
,
CronDelete
, and
CronList
. In a
session without the Task tools
, Claude Code doesn’t provide the task tools to subagents either, even when the subagent runs a different model. An in-process teammate follows your session the same way. To find out whether a split-pane teammate has the task tools, see
Task tool availability
.
​
Restrict which tools a subagent can use
To restrict tools, use the
tools
field as an allowlist or the
disallowedTools
field as a denylist. If both are set,
disallowedTools
is applied first, then
tools
is resolved against the remaining pool. A tool listed in both is removed.
This example uses
tools
to allow only Read, Grep, Glob, and Bash. The subagent can’t edit files, write files, or use any MCP tools:
---
name
:
safe-researcher
description
:
Research agent with restricted capabilities
tools
:
Read, Grep, Glob, Bash
---
This example uses
disallowedTools
to inherit the subagent’s tool pool except Write and Edit. The subagent keeps Bash, MCP tools, and the rest of its pool:
---
name
:
no-writes
description
:
Inherits the available tools except file writes
disallowedTools
:
Write, Edit
---
When nothing in the
tools
list resolves to a tool, for example because every entry is misspelled or names a tool that isn’t available to subagents, Claude Code usually refuses to launch the subagent and the Agent tool returns an error naming the unresolved entries; see
Agent would be spawned with zero tools
for the message and how to fix each entry.
The
tools
and
disallowedTools
fields also take entries for a whole MCP server:
Goal
Field
Example entry
Give the subagent every tool from one server
tools
mcp__github__*
Withhold one server’s tools
disallowedTools
mcp__github
or
mcp__github__*
Withhold every MCP tool from any server
disallowedTools
mcp__*
This example removes every tool from the
github
MCP server while keeping tools from other servers and the built-in tools in the subagent’s pool:
---
name
:
local-only
description
:
Inherits every tool except those from the github MCP server
disallowedTools
:
mcp__github
---
A
disallowedTools
entry with a specifier, such as
Bash(git push *)
, still removes the whole tool from the subagent, not only the matching commands. To keep Bash and block specific commands, add a
Bash deny rule
such as
Bash(git push *)
to
permissions.deny
in your settings. The rule applies to the main conversation and to subagents.
MCP server names that contain a double underscore
If a subagent gets none of the tools from an MCP server whose name contains
__
, such as
reports__v2
, check the subagent’s
mcp__
entries:
In
tools
: write
mcp__
followed by the
server’s whole name
and
__*
, as in
mcp__reports__v2__*
. Without the trailing
__*
,
mcp__reports__v2
matches none of that server’s tools.
In
disallowedTools
: look for
mcp__reports
or
mcp__reports__*
, the entries that withhold a server named
reports
. With either entry, the subagent loses every
reports__v2
tool as well, because those tool names also begin with
mcp__reports__
. To withhold only the
reports
server’s tools, list them one by one instead, such as
mcp__reports__run_query
.
​
Restrict which subagents can be spawned
When an agent runs as the main thread with
claude --agent
, it can spawn subagents using the Agent tool. To restrict which subagent types it can spawn, use
Agent(agent_type)
syntax in the
tools
field.
In version 2.1.63, the Task tool was renamed to Agent. Existing
Task(...)
references in settings and agent definitions still work as aliases.
---
name
:
coordinator
description
:
Coordinates work across specialized agents
tools
:
Agent(worker, researcher), Read, Bash
---
This is an allowlist: only the
worker
and
researcher
subagents can be spawned. If the agent tries to spawn any other type, the request fails and the agent sees only the allowed types in its prompt. To block specific agents while allowing all others, use
permissions.deny
instead.
To allow spawning any subagent without restrictions, use
Agent
without parentheses:
tools
:
Agent, Read, Bash
If you omit
Agent
from the
tools
list entirely, the agent can’t spawn any subagents with the Agent tool.
The
Agent(agent_type)
allowlist syntax applies only to an agent running as the main thread with
claude --agent
. In a subagent definition, listing
Agent
in
tools
lets that subagent spawn subagents of its own while the
depth limit
allows it, but any type list inside the parentheses is ignored.
​
Scope MCP servers to a subagent
Use the
mcpServers
field to give a subagent access to
MCP
servers that aren’t available in the main conversation. Inline servers defined here are connected when the subagent starts, subject to the
trust rule for the agent file’s folder
, and disconnected when it finishes. String references share the parent session’s connection.
The
mcpServers
field applies in both contexts where an agent file can run:
As a subagent, spawned through the Agent tool or an @-mention
As the main session, launched with
--agent
or the
agent
setting
When the agent is the main session, inline server definitions connect at startup alongside servers from
.mcp.json
and settings files, under the same
trust rule for the agent file’s folder
. In
/mcp
, a remote (HTTP or SSE) server you’ve used before can show the
cached
status
instead; Claude Code connects it when Claude first calls one of its tools.
Each entry in the list is either an inline server definition or a string referencing an MCP server already configured in your session:
---
name
:
browser-tester
description
:
Tests features in a real browser using Playwright
mcpServers
:
# Inline definition: scoped to this subagent only
-
playwright
:
type
:
stdio
command
:
npx
args
: [
"-y"
,
"@playwright/mcp@latest"
]
# Reference by name: reuses an already-configured server
-
github
---
Use the Playwright tools to navigate, screenshot, and interact with pages.
Inline definitions use the same schema as
.mcp.json
server entries, keyed by the server name, and support the
stdio
,
http
,
sse
, and
ws
types.
To keep an MCP server out of the main conversation entirely and avoid its tool descriptions consuming context there, define it inline here rather than in
.mcp.json
. The subagent gets the tools; the parent conversation doesn’t.
The MCP restrictions that apply to the main session also cover servers declared in subagent frontmatter:
--strict-mcp-config
and
--bare
Enterprise managed MCP configuration
allowedMcpServers
and
deniedMcpServers
policies
When one of these blocks a server, Claude Code skips it and shows a warning naming the blocked servers.
Managed-settings restrictions apply to every subagent regardless of how it is defined.
--strict-mcp-config
doesn’t filter servers you pass inline via
--agents
or the SDK
agents
option, since those are explicit caller input.
​
Trust required for inline MCP servers
Claude Code loads an
inline MCP server
from an agent file in your project’s
.claude/agents/
directory, or in an
--add-dir
directory’s
.claude/agents/
, only after you
trust the folder the agent file came from
. Before v2.1.238, Claude Code loaded these servers without checking trust.
Trust that doesn’t count
: a parent folder’s trust, and the automatic trust a
-p
or SDK session gets for
hooks in settings files
Until then
: Claude Code skips every inline server in that agent file and writes the exact
projects["<path>"].hasTrustDialogAccepted
key for
~/.claude.json
to the debug log
--add-dir
directories
: a directory outside your trusted workspace’s repository needs its own trust entry, since its
.claude/agents/
files don’t inherit your workspace’s trust
Claude Code loads two kinds of server without checking trust for the folder the agent file came from:
A name that references a server you already configured
An inline server in an agent file from
~/.claude/agents/
, in one you pass with
--agents
or the SDK
agents
option, or in one that managed settings supplies
​
Permission modes
Set
permissionMode
to choose the permission mode a subagent runs in. Use the modes’ config values, so Manual mode is
default
. If you leave it unset, the subagent inherits the main conversation’s
permission mode
.
The main conversation’s permission mode decides whether Claude Code uses the value you set:
When the main conversation is in
bypassPermissions
,
acceptEdits
, or
auto mode
, the subagent runs in that same mode and Claude Code ignores the
permissionMode
you set. Under auto mode, the classifier evaluates the subagent’s tool calls with the main conversation’s block and allow rules. When the subagent finishes, the classifier also reviews its work and its final report before the report is delivered, as
How auto mode handles subagents
describes.
When the main conversation is in
plan
mode, the subagent stays in plan mode whichever
permissionMode
you set, unless it runs as an
agent team teammate
under the
agent teams rules
. If you set
dontAsk
, the subagent also doesn’t prompt you: an action that plan mode would ask you to approve is denied instead.
When the main conversation is in
default
or
dontAsk
mode, the subagent runs in the permission mode you set. It keeps the main conversation’s permission mode instead in these cases:
You set
bypassPermissions
. The
bypassPermissions
exception requires Claude Code v2.1.267 or later.
You set
auto
and
auto mode isn’t available
to the subagent, such as when a settings file sets
disableAutoMode
or the subagent’s model doesn’t support auto mode.
permissionMode
accepts these values, and
manual
as an alias for
default
:
Mode
Behavior
default
Manual mode: prompts for permission
acceptEdits
Auto-accept file edits and common filesystem commands for paths in the working directory or
additionalDirectories
auto
Auto mode
: a background classifier reviews commands and protected-directory writes
dontAsk
Auto-denies calls that would prompt, though a
mod
you installed can still approve
some of those calls
. Explicitly allowed tools still work.
AskUserQuestion
, MCP tools marked
requiresUserInteraction
,
reads from network paths
, and connector tools
your organization set to
ask
in sessions where that setting reaches Claude Code are denied even if you’ve allowed them
bypassPermissions
Skip permission prompts
. A subagent runs in this mode only when the main conversation does
plan
Plan mode (read-only exploration)
​
Preload skills into subagents
Use the
skills
field to inject skill content into a subagent’s context at startup. This gives the subagent domain knowledge without requiring it to discover and load skills during execution.
---
name
:
api-developer
description
:
Implement API endpoints following team conventions
skills
:
-
api-conventions
-
error-handling-patterns
---
Implement API endpoints. Follow the conventions and patterns from the preloaded skills.
The full content of each listed skill is injected into the subagent’s context at startup, up to the first 32 distinct names in the list. This field controls which skills are preloaded, not which skills the subagent can access: without it, the subagent can still discover and invoke project, user, and plugin skills through the Skill tool during execution. To prevent a subagent from invoking skills entirely, omit
Skill
from the
tools
list or add it to
disallowedTools
.
You can’t preload skills that set
disable-model-invocation: true
, since preloading draws from the same set of skills Claude can invoke. This includes the bundled
/verify
skill, which Claude can’t run on its own.
If a listed skill is missing or disabled, for example by your organization’s policy, Claude Code skips it and logs a warning to the debug log.
This is the inverse of
running a skill in a subagent
. With
skills
in a subagent, the subagent controls the system prompt and loads skill content. With
context: fork
in a skill, the skill content is injected into the agent you specify. In both cases the subagent starts without your conversation history.
​
Enable persistent memory
The
memory
field gives the subagent a persistent directory that survives across conversations. The subagent uses this directory to build up knowledge over time, such as codebase patterns, debugging insights, and architectural decisions.
---
name
:
code-reviewer
description
:
Reviews code for quality and best practices
memory
:
user
---
You are a code reviewer. As you review code, update your agent memory with
patterns, conventions, and recurring issues you discover.
Choose a scope based on how broadly the memory should apply:
Scope
Location
Use when
user
~/.claude/agent-memory/<name-of-agent>/
the subagent should remember learnings across all projects
project
.claude/agent-memory/<name-of-agent>/
the subagent’s knowledge is project-specific and shareable via version control
local
.claude/agent-memory-local/<name-of-agent>/
the subagent’s knowledge is project-specific but shouldn’t be checked into version control
Subagent memory is part of
auto memory
: if you turn auto memory off, with the
autoMemoryEnabled
setting or
CLAUDE_CODE_DISABLE_AUTO_MEMORY
, the
memory
field has no effect and the subagent launches without the memory instructions or the memory tool access described below.
When memory is enabled:
The subagent’s system prompt includes instructions for reading and writing to the memory directory.
The subagent’s system prompt also includes the first 200 lines or 25KB of
MEMORY.md
in the memory directory, whichever comes first, with instructions to curate
MEMORY.md
if it exceeds that limit.
Read, Write, and Edit tools are automatically enabled so the subagent can manage its memory files.
Persistent memory tips
project
is the recommended default scope. It makes subagent knowledge shareable via version control.
Ask the subagent to consult its memory before starting work: “Review this PR, and check your memory for patterns you’ve seen before.”
Ask the subagent to update its memory after completing a task: “Now that you’re done, save what you learned to your memory.” Over time, this builds a knowledge base that makes the subagent more effective.
Include memory instructions directly in the subagent’s markdown file so it proactively maintains its own knowledge base:
Update your agent memory as you discover codepaths, patterns, library
locations, and key architectural decisions. This builds up institutional
knowledge across conversations. Write concise notes about what you found
and where.
​
Conditional rules with hooks
For more dynamic control over tool usage, use
PreToolUse
hooks to validate operations before they execute. This is useful when you need to allow some operations of a tool while blocking others.
This example creates a subagent that only allows read-only database queries. The
PreToolUse
hook runs the script specified in
command
before each Bash command executes:
---
name
:
db-reader
description
:
Execute read-only database queries
tools
:
Bash
hooks
:
PreToolUse
:
-
matcher
:
"Bash"
hooks
:
-
type
:
command
command
:
"./scripts/validate-readonly-query.sh"
---
Claude Code
passes hook input as JSON
via stdin to hook commands. The validation script reads this JSON, extracts the Bash command, and
exits with code 2
to block write operations:
#!/bin/bash
# ./scripts/validate-readonly-query.sh
INPUT
=
$(
cat
)
COMMAND
=
$(
echo
"
$INPUT
"
|
jq
-r
'.tool_input.command // empty'
)
# Block SQL write operations (case-insensitive)
if
ec

## Source (hooks): https://docs.claude.com/en/docs/claude-code/hooks

Hooks reference - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
For a quickstart guide with examples, see
Automate actions with hooks
.
Hooks are user-defined shell commands, HTTP endpoints, MCP tool calls, LLM prompts, or subagents that execute automatically at specific points in Claude Code’s lifecycle. Claude Code fires the same hook events wherever it runs: sessions in the terminal, IDE extensions, the
Desktop app
, and
cloud sessions
. Use this reference to look up event schemas, configuration options, JSON input/output formats, and advanced features like async hooks, HTTP hooks, and MCP tool hooks.
A plugin can also register hooks as JavaScript functions that Claude Code calls in its own process, which can draw in the interface as well as act on events. A plugin that does is a
mod
, and those function hooks are covered in
React to events
rather than here. The hooks on this page keep working alongside mods.
​
Hook lifecycle
Claude Code runs hooks at specific points during a session. When an event fires and a matcher matches, Claude Code passes JSON context about the event to your hook handler. For command hooks, input arrives on stdin. For HTTP hooks, it arrives as the POST request body. Your handler can then inspect the input, take action, and optionally return a decision.
Events fall into three cadences:
per session:
SessionStart
and
SessionEnd
per turn:
UserPromptSubmit
,
Stop
, and
StopFailure
on every tool call inside the agentic loop:
PreToolUse
and
PostToolUse
, except
EndConversation
calls, which skip both
The table below summarizes when each event fires. The
Hook events
section documents the full input schema and decision control options for each one.
Event
When it fires
SessionStart
When a session begins or resumes
Setup
When you start Claude Code with
--init-only
, or with
--init
or
--maintenance
in
-p
mode. For one-time preparation in CI or scripts
UserPromptSubmit
When a prompt is submitted, before Claude processes it. Also fires on
turns Claude Code starts on its own
UserPromptExpansion
When a user-typed command expands into a prompt, before it reaches Claude. Can block the expansion
PreToolUse
Before a tool call executes. Can block it
PermissionRequest
When a tool call needs a permission decision
PermissionDenied
When auto mode denies a tool call, including denials without a classifier verdict. Use JSON
hookSpecificOutput.retry: true
to tell the model it may retry the denied tool call. Claude Code ignores
retry
when the classifier produced no verdict
PostToolUse
After a tool call succeeds
PostToolUseFailure
After a tool call fails
PostToolBatch
After a full batch of parallel tool calls resolves, before the next model call
Notification
When Claude Code sends a notification
MessageDisplay
While assistant message text is displayed
SubagentStart
When a subagent is spawned
SubagentStop
When a subagent finishes
TaskCreated
When a task is being created via
TaskCreate
TaskCompleted
When a task is being marked as completed
Stop
When Claude finishes responding
StopFailure
When the turn ends due to an API error
TeammateIdle
When an
agent team
teammate is about to go idle
InstructionsLoaded
When a CLAUDE.md or
.claude/rules/*.md
file is loaded into context. Fires at session start and when files are lazily loaded during a session
ConfigChange
When a configuration file changes during a session
CwdChanged
When the working directory changes, for example when Claude executes a
cd
command. Useful for reactive environment management with tools like direnv
DirectoryAdded
When a working directory is added mid-session via
/add-dir
or the SDK
register_repo_root
control request
FileChanged
When a watched file changes on disk. The
matcher
field specifies which filenames to watch
WorktreeCreate
When a worktree is being created via
--worktree
,
isolation: "worktree"
, or for a background session. Replaces default git behavior
WorktreeRemove
When a worktree that a
WorktreeCreate
hook created is being removed
PreCompact
Before context compaction
PostCompact
After context compaction completes
PreModelSwitch
Before Claude Code applies a model switch that you or a client requested. Can block the switch
PostModelSwitch
After the session’s model changes, including changes Claude Code makes on its own, such as restoring the model when you resume a session
Elicitation
When an MCP server requests user input during a tool call
ElicitationResult
After a user responds to an MCP elicitation, before the response is sent back to the server
SessionEnd
When a session terminates
​
How a hook resolves
To see how the event, the matcher, and the handler fit together, consider this
PreToolUse
hook that blocks destructive shell commands.
macOS/Linux
Windows (PowerShell)
The
matcher
narrows to Bash tool calls and the
if
condition narrows further to Bash subcommands matching
rm *
, so
block-rm.sh
only spawns when both filters match:
{
"hooks"
: {
"PreToolUse"
: [
{
"matcher"
:
"Bash"
,
"hooks"
: [
{
"type"
:
"command"
,
"if"
:
"Bash(rm *)"
,
"command"
:
"${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.sh"
,
"args"
: []
}
]
}
]
}
}
The script reads the JSON input from stdin, extracts the command, and returns a
permissionDecision
of
"deny"
if it contains
rm -rf
. Save it to
.claude/hooks/block-rm.sh
in your project and make it executable with
chmod +x .claude/hooks/block-rm.sh
so Claude Code can run it:
#!/bin/bash
# .claude/hooks/block-rm.sh
COMMAND
=
$(
jq
-r
'.tool_input.command'
)
if
echo
"
$COMMAND
"
|
grep
-q
'rm -rf'
;
then
jq
-n
'{
hookSpecificOutput: {
hookEventName: "PreToolUse",
permissionDecision: "deny",
permissionDecisionReason: "Destructive command blocked by hook"
}
}'
else
exit
0
# no decision; normal permission flow applies
fi
This script, like the other Bash examples on this page that parse JSON input, uses
jq
, so install
jq
and make sure it is on your
PATH
before trying them.
The matcher
Bash|PowerShell
covers the
PowerShell tool
as well as Bash. A single
if
rule matches only one tool’s calls, so each tool gets its own handler: the first narrows to Bash subcommands matching
rm *
, the second to PowerShell commands matching
Remove-Item *
. Both run the same script through
powershell.exe
:
{
"hooks"
: {
"PreToolUse"
: [
{
"matcher"
:
"Bash|PowerShell"
,
"hooks"
: [
{
"type"
:
"command"
,
"if"
:
"Bash(rm *)"
,
"command"
:
"powershell.exe"
,
"args"
: [
"-NoProfile"
,
"-ExecutionPolicy"
,
"Bypass"
,
"-File"
,
"${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.ps1"
]
},
{
"type"
:
"command"
,
"if"
:
"PowerShell(Remove-Item *)"
,
"command"
:
"powershell.exe"
,
"args"
: [
"-NoProfile"
,
"-ExecutionPolicy"
,
"Bypass"
,
"-File"
,
"${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.ps1"
]
}
]
}
]
}
}
The
-NoProfile
flag skips loading your PowerShell profile so the hook starts fast, and
-ExecutionPolicy Bypass
lets PowerShell run the local script file.
The script reads the JSON input from stdin, extracts the command, and returns a
permissionDecision
of
"deny"
if it contains
rm -rf
or
Remove-Item
followed by
-Recurse
. Save it to
.claude/hooks/block-rm.ps1
in your project:
# .claude/hooks/block-rm.ps1
$callInput
=
[
Console
]::
In
.ReadToEnd()
|
ConvertFrom-Json
$command
=
$callInput
.tool_input.command
if
(
$command
-match
'rm -rf|Remove-Item.*-Recurse'
) {
@
{
hookSpecificOutput
=
@
{
hookEventName
=
"PreToolUse"
permissionDecision
=
"deny"
permissionDecisionReason
=
"Destructive command blocked by hook"
}
}
|
ConvertTo-Json
}
else
{
exit
0
# no decision; normal permission flow applies
}
Now suppose Claude Code decides to run
Bash "rm -rf /tmp/build"
against the macOS/Linux config. Here’s what happens:
1
Event fires
The
PreToolUse
event fires. Claude Code sends the tool input as JSON on stdin to the hook:
{
"tool_name"
:
"Bash"
,
"tool_input"
: {
"command"
:
"rm -rf /tmp/build"
},
...
}
2
Matcher checks
The matcher
"Bash"
matches the tool name, so this hook group activates. If you omit the matcher or use
"*"
, the group activates on every occurrence of the event.
3
If condition checks
The
if
condition
"Bash(rm *)"
matches because
rm -rf /tmp/build
is a subcommand matching
rm *
, so this handler spawns. If the command had been
npm test
, the
if
check would fail and
block-rm.sh
would never run, avoiding the process spawn overhead. The
if
field is optional; without it, every handler in the matched group runs.
4
Hook handler runs
The script inspects the full command and finds
rm -rf
, so it prints a decision to stdout:
{
"hookSpecificOutput"
: {
"hookEventName"
:
"PreToolUse"
,
"permissionDecision"
:
"deny"
,
"permissionDecisionReason"
:
"Destructive command blocked by hook"
}
}
If the command had been a safer
rm
variant like
rm file.txt
, the script would hit
exit 0
instead. Exit code 0 with no output means the hook has no decision to report, so the tool call continues through the normal
permission flow
. The hook can deny the call, but staying silent doesn’t approve it.
5
Claude Code acts on the result
Claude Code reads the JSON decision, blocks the tool call, and shows Claude the reason.
The
Configuration
section below documents the full schema, and each
hook event
section documents what input your command receives and what output it can return.
​
Configuration
Hooks are defined in JSON settings files. The configuration has three levels of nesting:
Choose a
hook event
to respond to, like
PreToolUse
or
Stop
Add a
matcher group
to filter when it fires, like “only for the Bash tool”
Define one or more
hook handlers
to run when matched
See
How a hook resolves
above for a complete walkthrough with an annotated example.
This page uses specific terms for each level:
hook event
for the lifecycle point,
matcher group
for the filter, and
hook handler
for the shell command, HTTP endpoint, MCP tool, prompt, or agent that runs. “Hook” on its own refers to the general feature.
​
Hook locations
Where you define a hook determines its scope:
Location
Scope
Shareable
~/.claude/settings.json
All your projects
No, local to your machine
.claude/settings.json
Single project
Yes, can be committed to the repo
.claude/settings.local.json
Single project
No, gitignored when Claude Code saves a setting to it
Managed policy settings
Organization-wide
Yes, admin-controlled
Plugin
hooks/hooks.json
When plugin is enabled
Yes, bundled with the plugin
Skill
frontmatter
The rest of the session once the skill is invoked. See
Hooks in skills and agents
Yes, defined in the skill file
Subagent
frontmatter
While that subagent is running
Yes, defined in the subagent file
Cloud sessions
don’t read your local
~/.claude/settings.json
. In a
self-hosted environment
, Claude Code also runs the hooks the operator seeded from the runner host’s
~/.claude/
, and it runs the hooks in the runner image’s managed settings file when that file is among the
managed sources Claude Code applies
, which by default means only when neither server-managed settings nor an MDM-delivered Claude Code policy supplies the managed tier. See
what carries over from your setup
for which settings files and plugins, and so which hooks, reach a cloud session.
For details on settings file resolution, see
settings
.
Hooks from settings files, managed policy settings, and plugins also run inside
subagents
. When a subagent calls a tool, tool events such as
PreToolUse
and
PostToolUse
fire the same configured hooks as in the main conversation, and the input carries the
agent_id
and
agent_type
common input fields
that identify the subagent.
Administrators can use
allowManagedHooksOnly
in
managed settings
to restrict which hooks run:
Your user, project, local, and plugin hooks are blocked. Hooks from plugins force-enabled in managed settings
enabledPlugins
are exempt
Claude Code also narrows your
statusLine
,
fileSuggestion
, and
subagentStatusLine
settings to managed settings
Claude Code also disables plugins with a
command
source
, including plugins force-enabled in managed settings
enabledPlugins
, unless
disableCommandPluginSources
is explicitly set to
false
.
command
sources require Claude Code v2.1.229 or later
Claude Code also blocks marketplace
headersHelper
commands
unless
disableCommandPluginSources
is explicitly set to
false
, except for a marketplace that managed settings themselves declare
See
what runs under
allowManagedHooksOnly
.
Hook entries merge across settings levels rather than replacing each other: user, project, and local settings add their own hooks without removing managed ones, and the
disableAllHooks
setting can’t disable managed hooks from outside managed settings.
The
HTTP hook allowlists
apply to hooks from every source, including managed policy settings:
allowedHttpHookUrls
: when defined at any settings level, Claude Code runs an HTTP hook handler only if its URL matches the merged allowlist
httpHookAllowedEnvVars
: when defined, Claude Code interpolates only the environment variables on that list into hook headers
​
Matcher patterns
The
matcher
field filters when hooks fire. How a matcher is evaluated depends on the characters it contains:
Matcher value
Evaluated as
Example
"*"
,
""
, or omitted
Match all
fires on every occurrence of the event
Only letters, digits,
_
,
-
, spaces,
,
, and
|
Exact string, or list of exact strings separated by
|
or
,
with optional surrounding whitespace
Bash
matches only the Bash tool;
Edit|Write
and
Edit, Write
each match either tool exactly;
code-reviewer
matches only that agent type
Contains any other character
JavaScript regular expression, unanchored
^Notebook
matches any tool whose name starts with
Notebook
;
mcp__memory__.*
matches every tool from the
memory
server
A matcher on the regular-expression path is tested with JavaScript’s
RegExp.prototype.test
, which succeeds on a match anywhere in the value.
Edit.*
matches both
Edit
and
NotebookEdit
; wrap the pattern in
^
and
$
, as in
^Edit$
, when you need a whole-string match.
FileChanged
and
StopFailure
use a narrower exact-match set of letters, digits,
_
, and
|
only. A hyphen, space, or comma in a matcher for those two events keeps it on the regular-expression path, and only
|
separates alternatives. Every other event with matcher support in the table that follows accepts
|
or
,
.
The
FileChanged
event doesn’t follow these rules when building its watch list. See
FileChanged
.
Each event type matches on a different field:
Event
What the matcher filters
Example matcher values
PreToolUse
,
PostToolUse
,
PostToolUseFailure
,
PermissionRequest
,
PermissionDenied
tool name
Bash
,
Edit|Write
,
mcp__.*
SessionStart
how the session started
startup
,
resume
,
clear
,
compact
,
fork
Setup
which CLI flag triggered setup
init
,
maintenance
SessionEnd
why the session ended
clear
,
resume
,
logout
,
prompt_input_exit
,
other
Notification
notification type
permission_prompt
,
idle_prompt
,
auth_success
,
elicitation_dialog
,
elicitation_url_dialog
,
elicitation_complete
,
elicitation_response
,
agent_needs_input
,
agent_completed
,
quota_auto_resume_fired
,
quota_auto_resume_stale
,
quota_auto_resume_disabled
,
plugin_notification
SubagentStart
agent type
general-purpose
,
Explore
,
Plan
, custom agent names, or plugin-scoped names like
^my-plugin:reviewer$
PreCompact
,
PostCompact
what triggered compaction
manual
,
auto
PreModelSwitch
,
PostModelSwitch
canonical name of the model the session switches to, as described under
PreModelSwitch
claude-opus-5
,
claude-opus-4-6|claude-opus-5
,
.*opus.*
SubagentStop
agent type
same values as
SubagentStart
ConfigChange
configuration source
user_settings
,
project_settings
,
local_settings
,
policy_settings
,
skills
CwdChanged
no matcher support
always fires on every occurrence
DirectoryAdded
how the directory was added
slash_command
,
register_repo_root
FileChanged
literal filenames to watch (see
FileChanged
)
.envrc|.env
StopFailure
error type
rate_limit
,
overloaded
,
authentication_failed
,
oauth_org_not_allowed
,
account_on_hold
,
billing_error
,
invalid_request
,
model_not_found
,
server_error
,
max_output_tokens
,
cloud_credential_error
,
unknown
InstructionsLoaded
load reason
session_start
,
nested_traversal
,
path_glob_match
,
include
,
compact
UserPromptExpansion
command name
your skill or command names
Elicitation
MCP server name
your configured MCP server names
ElicitationResult
MCP server name
same values as
Elicitation
UserPromptSubmit
,
PostToolBatch
,
Stop
,
TeammateIdle
,
TaskCreated
,
TaskCompleted
,
WorktreeCreate
,
WorktreeRemove
,
MessageDisplay
no matcher support
always fires on every occurrence
Matching
StopFailure
on
cloud_credential_error
requires Claude Code v2.1.267 or later, the first version that reports credential-load failures under that value rather than
server_error
or
unknown
.
For most events, Claude Code evaluates the matcher against a field from the
JSON input
it sends to your hook on stdin. For tool events, that field is
tool_name
. For
PreModelSwitch
and
PostModelSwitch
, Claude Code evaluates the matcher against the canonical name it derives from
to_model
, as described under
PreModelSwitch
. Each
hook event
section lists the full set of matcher values and the input schema for that event.
This example runs a linting script only when Claude writes or edits a file:
{
"hooks"
: {
"PostToolUse"
: [
{
"matcher"
:
"Edit|Write"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"/path/to/lint-check.sh"
}
]
}
]
}
}
If you add a
matcher
field to an event without matcher support, it is silently ignored.
For tool events, you can filter more narrowly by setting the
if
field
on individual hook handlers.
if
uses
permission rule syntax
to match against the tool name and arguments together, so
"Bash(git *)"
runs when any subcommand of the Bash input matches
git *
and
"Edit(*.ts)"
runs only for TypeScript files.
​
Match MCP tools
MCP
server tools appear as regular tools in tool events (
PreToolUse
,
PostToolUse
,
PostToolUseFailure
,
PermissionRequest
,
PermissionDenied
), so you can match them the same way you match any other tool name.
MCP tools follow the naming pattern
mcp__<server>__<tool>
, for example:
mcp__memory__create_entities
: Memory server’s create entities tool
mcp__filesystem__read_file
: Filesystem server’s read file tool
mcp__github__search_repositories
: GitHub server’s search tool
To match every tool from a server, append
.*
to the server prefix. The
.*
is required: a matcher like
mcp__memory
or
mcp__brave-search
contains only exact-match characters, so it is compared as an exact string and matches no tool.
mcp__memory__.*
matches all tools from the
memory
server
mcp__brave-search__.*
matches all tools from a server whose name contains a hyphen
mcp__.*__write.*
matches any tool whose name starts with
write
from any server
Tools from a
plugin-bundled MCP server
use a scoped server segment that includes the plugin name:
mcp__plugin_<plugin-name>_<server-name>__<tool>
. A matcher written against the bare server key never fires for these tools. For a plugin named
my-plugin
that bundles a server under the key
db
, a
query
tool appears as
mcp__plugin_my-plugin_db__query
, so the matcher for every tool from that server is
mcp__plugin_my-plugin_db__.*
. Use the same scoped tool name in a handler’s
if
field
. See
Plugin-provided MCP servers
for how the scoped name is built.
This example logs all memory server operations and validates write operations from any MCP server:
{
"hooks"
: {
"PreToolUse"
: [
{
"matcher"
:
"mcp__memory__.*"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"echo 'Memory operation initiated' >> ~/mcp-operations.log"
}
]
},
{
"matcher"
:
"mcp__.*__write.*"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"/home/user/scripts/validate-mcp-write.py"
}
]
}
]
}
}
​
Hook handler fields
Each object in the inner
hooks
array is a hook handler: the shell command, HTTP endpoint, MCP tool, LLM prompt, or agent that runs when the matcher matches. There are five types:
Command hooks
(
type: "command"
): run a shell command. Your script receives the event’s
JSON input
on stdin and communicates results back through exit codes and stdout.
HTTP hooks
(
type: "http"
): send the event’s JSON input as an HTTP POST request to a URL. The endpoint communicates results back through the response body using the same
JSON output format
as command hooks.
MCP tool hooks
(
type: "mcp_tool"
): call a tool on a configured
MCP server
. The tool’s text output is treated like command-hook stdout.
Prompt hooks
(
type: "prompt"
): send a prompt to a Claude model for single-turn evaluation. The model returns its decision as JSON. See
Prompt-based hooks
.
Agent hooks
(
type: "agent"
): spawn a subagent that can use tools like Read, Grep, and Glob to verify conditions before returning a decision. Agent hooks are experimental and may change. See
Agent-based hooks
.
When an event fires, its matching hooks run in parallel. If more than 12 of them are prompt or agent hooks, 12 of those run at once and the rest start as running ones finish. Each waiting hook’s
timeout
starts counting when that hook starts.
If you define the same handler in more than one settings file, it runs once. A plugin’s or skill’s copy of the same handler stays separate.
Handlers run in the current directory with Claude Code’s environment. If the current directory no longer exists, for example a worktree or temp directory that another shell deleted mid-session, Claude Code runs command hooks from the first of these that still exists: the directory the session started in, the project root, your home directory, or the system temp directory. Claude Code records a warning naming the fallback directory in the
debug log
. For a worktree session that you start from the desktop app, see
What worktrees share with the main checkout
.
The
$CLAUDE_CODE_REMOTE
environment variable is
"true"
in remote web environments and not set in the local CLI. Claude Code v2.1.199 and later sets
$CLAUDE_CODE_BRIDGE_SESSION_ID
to the
Remote Control
session ID while the local session has an active Remote Control connection.
​
Common fields
These fields apply to all hook types:
Field
Required
Description
type
yes
"command"
,
"http"
,
"mcp_tool"
,
"prompt"
, or
"agent"
if
no
Permission rule syntax
to filter when this hook runs, such as
"Bash(git *)"
or
"Edit(*.ts)"
. The hook command only runs if the tool call matches the pattern. See the
Bash matching table
for how Bash patterns evaluate against subcommands,
$()
, and backticks. Only evaluated on tool events:
PreToolUse
,
PostToolUse
,
PostToolUseFailure
,
PermissionRequest
, and
PermissionDenied
. On other events, a hook with
if
set never runs
timeout
no
Seconds before canceling. Claude Code doesn’t enforce it on a command hook you run with
async: true
. Defaults: 600 for
command
,
http
, and
mcp_tool
; 30 for
prompt
; 60 for
agent
. Claude Code lowers the
command
,
http
, and
mcp_tool
default to 30 on
UserPromptSubmit
,
PreModelSwitch
, and
PostModelSwitch
, and to 10 on
MessageDisplay
.
SessionEnd
hooks share a 1.5-second budget; if your settings set a longer per-hook
timeout
, Claude Code raises the budget to match, up to 60 seconds
statusMessage
no
Custom spinner message displayed while the hook runs
once
no
If
true
, Claude Code removes the hook after its first successful run. A run that fails, blocks with exit code 2, or times out leaves the hook in place, so it runs again on the next matching event. Only honored for hooks declared in
skill frontmatter
; ignored in settings files and agent frontmatter
The
if
field holds exactly one permission rule. There is no
&&
,
||
, or list syntax for combining rules; to apply multiple conditions, define a separate hook handler for each.
In an
if
condition for a file tool, a single-segment directory pattern like
"Edit(src/**)"
matches only the
src
directory in the working directory and the files under it. To match a directory named
src
at any depth, write
"Edit(**/src/**)"
.
​
How
if
patterns match Bash commands
For Bash patterns in the
if
field
, whether your hook command runs depends on the shape of the pattern and the Bash command Claude is invoking. Leading
VAR=value
assignments are stripped before matching.
if
pattern
Bash command
Hook runs?
Why
Bash(git *)
FOO=bar git push
yes
leading assignments are stripped;
git push
matches
Bash(git *)
npm test && git push
yes
each subcommand is checked;
git push
matches
Bash(rm *)
echo $(rm -rf /)
yes
commands inside
$()
and backticks are checked;
rm -rf /
matches
Bash(rm *)
echo $(date)
no
no subcommand matches
rm *
Bash(git push *)
echo $(date)
yes
patterns that specify more than the command name run the hook anyway on
$()
, backticks, or
$VAR
When Claude Code can’t determine which commands the Bash input runs, it runs your hook regardless of the pattern. Because the
if
filter is best-effort, use the
permission system
rather than a hook to enforce a hard allow or deny.
​
Command hook fields
In addition to the
common fields
, command hooks accept these fields:
Field
Required
Description
command
yes
Shell command to execute. With
args
, the executable to spawn directly. See
Exec form and shell form
args
no
Argument list. When present,
command
is resolved as an executable and spawned directly with
args
as the argument vector, with no shell involved. See
Exec form and shell form
async
no
If
true
, runs in the background without blocking. See
Run hooks in the background
asyncRewake
no
If
true
, runs in the background and wakes Claude on exit code 2. The hook’s stderr, or stdout if stderr is empty, is shown to Claude as a
system reminder
so it can react to a long-running background failure
shell
no
Shell to use for this hook. Accepts
"bash"
or
"powershell"
. Defaults to
"bash"
, or to
"powershell"
on Windows when Git Bash isn’t installed. Setting
"powershell"
runs the command via PowerShell on Windows. Does not require
CLAUDE_CODE_USE_POWERSHELL_TOOL
since hooks spawn PowerShell directly. Ignored when
args
is set
onFailure
no
Whether the action that triggered the hook goes ahead when the hook fails:
"continue"
or
"block"
. See
Block the action when a hook fails
for
"block"
and for leaving the field unset. Requires Claude Code v2.1.295 or later
Exec form and shell form
A command hook runs as exec form when
args
is set, and shell form when
args
is omitted. Set
args
whenever the hook references a
path placeholder
, since each element is passed as one argument with no quoting. Omit
args
when you need shell features like pipes or
&&
, or when neither concern applies.
Exec form
runs when
args
is present. Claude Code resolves
command
as an executable on
PATH
and spawns it directly with
args
as the argument vector. There is no shell, so each
args
element is one argument exactly as written, and path placeholders like
${CLAUDE_PLUGIN_ROOT}
are substituted into
command
and into each
args
element as plain strings. Special characters such as apostrophes,
$
, and backticks pass through verbatim because there is no shell to interpret them. No shell tokenization happens on any platform.
Shell form
runs when
args
is absent. The
command
string is passed to a shell:
sh -c
on macOS and Linux, Git Bash on Windows, or PowerShell when Git Bash isn’t installed. Set the
shell
field to choose explicitly. The shell tokenizes the string, expands variables, and interprets pipes,
&&
, redirects, and globs.
On Windows, exec form requires
command
to resolve to a real executable such as a
.exe
. The
.cmd
and
.bat
shims that npm, npx, eslint, and other tools install in
node_modules/.bin
are not executables and can’t be spawned without a shell. To run them in exec form, invoke the underlying script with
node
directly, for example
"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/node_modules/eslint/bin/eslint.js"]
. The
node
plus script-path pattern works on every platform because
node.exe
is a real binary. To run a
.cmd
or
.bat
shim by name, use shell form.
This example runs a Node script bundled with a plugin. Exec form passes the resolved script path as one argument with no quoting:
{
"type"
:
"command"
,
"command"
:
"node"
,
"args"
: [
"${CLAUDE_PLUGIN_ROOT}/scripts/format.js"
,
"--fix"
]
}
The equivalent shell form needs quoting to handle paths with spaces or special characters:
{
"type"
:
"command"
,
"command"
:
"node
\"
${CLAUDE_PLUGIN_ROOT}
\"
/scripts/format.js --fix"
}
Both forms support the same
path placeholders
, and both export them as the environment variables
CLAUDE_PROJECT_DIR
,
CLAUDE_PLUGIN_ROOT
, and
CLAUDE_PLUGIN_DATA
on the spawned process, so a script can read
process.env.CLAUDE_PLUGIN_ROOT
regardless of how it was launched.
Plugin hooks additionally substitute
${user_config.*}
values, in exec form only: the value is substituted into
command
and into each
args
element as a plain string, so no shell re-parses it.
A shell-form plugin hook whose
command
references
${user_config.*}
fails with an
error
instead of running. To use an option value from a shell-form hook, read the
$CLAUDE_PLUGIN_OPTION_<KEY>
environment variable, such as
$CLAUDE_PLUGIN_OPTION_WEBHOOK_URL
for a
webhook_url
option, or set
args
to switch the hook to exec form. Before v2.1.207, shell-form plugin hook commands also substituted
${user_config.*}
.
In exec form,
command
is the executable name or path only. If
command
is a bare name with no path separator and contains whitespace alongside
args
, Claude Code logs a warning because the spawn will fail: there is no executable named
node script.js
. Move the extra tokens into
args
. Absolute paths with spaces, such as
C:\Program Files\nodejs\node.exe
, are a single valid executable and don’t trigger the warning.
​
HTTP hook fields
In addition to the
common fields
, HTTP hooks accept these fields:
Field
Required
Description
url
yes
URL to send the POST request to
headers
no
Additional HTTP headers as key-value pairs. Values support environment variable interpolation using
$VAR_NAME
or
${VAR_NAME}
syntax. Only variables listed in
allowedEnvVars
are resolved
allowedEnvVars
no
List of environment variable names that may be interpolated into header values. References to unlisted variables are replaced with empty strings. Required for any env var interpolation to work
onFailure
no
What happens to the action when the hook fails:
"continue"
, the default, or
"block"
. See
Block the action when a hook fails
. Requires Claude Code v2.1.295 or later
Claude Code sends the hook’s
JSON input
as the POST request body with
Content-Type: application/json
. The response body uses the same
JSON output format
as command hooks.
Error handling differs from command hooks; see
HTTP response handling
.
This example sends
PreToolUse
events to a local validation service, authenticating with a token from the
MY_TOKEN
environment variable:
{
"hooks"
: {
"PreToolUse"
: [
{
"matcher"
:
"Bash"
,
"hooks"
: [
{
"type"
:
"http"
,
"url"
:
"http://localhost:8080/hooks/pre-tool-use"
,
"timeout"
:
30
,
"headers"
: {
"Authorization"
:
"Bearer $MY_TOKEN"
},
"allowedEnvVars"
: [
"MY_TOKEN"
]
}
]
}
]
}
}
​
MCP tool hook fields
In addition to the
common fields
, MCP tool hooks accept these fields:
Field
Required
Description
server
yes
Name of a configured MCP server. For a
plugin-bundled server
, this is the scoped name
plugin:<plugin-name>:<server-name>
, such as
plugin:my-plugin:db
, not the bare server key
tool
yes
Name of the tool to call on that server
input
no
Arguments passed to the tool. String values support
${path}
substitution from the hook’s
JSON input
, such as
"${tool_input.file_path}"
This example calls the
security_scan
tool on the
my_server
MCP server after each
Write
or
Edit
, passing the edited file’s path:
{
"hooks"
: {
"PostToolUse"
: [
{
"matcher"
:
"Write|Edit"
,
"hooks"
: [
{
"type"
:
"mcp_tool"
,
"server"
:
"my_server"
,
"tool"
:
"security_scan"
,
"input"
: {
"file_path"
:
"${tool_input.file_path}"
}
}
]
}
]
}
}
How the tool’s result is read
Claude Code reads the tool’s text content the same way it reads command-hook stdout, following the
parsing rule under exit code 0
. If the tool returns
isError: true
, the hook produces a non-blocking error and execution continues.
When the server is still connecting
On events where a hook can block or change the result, such as
PreToolUse
or
Stop
, Claude Code waits for a connecting server before it calls the tool, for at most
MCP_TIMEOUT
and within the hook’s own
timeout
. On observational events, such as
Notification
or
SessionEnd
, it doesn’t wait.
A server showing the
cached
status
connects when the hook calls its tool. If the server isn’t connected at that point, the hook produces a non-blocking error and execution continues. The hook never starts an OAuth flow, so
authenticate the server from
/mcp
first.
Events that fire before MCP servers are available
SessionStart
at launch, including with
--continue
or
--resume
, and every
Setup
event fire before the session’s MCP servers are available to hooks. Claude Code skips their
mcp_tool
hooks without calling the tool, and the
debug log
records
mcp_tool hooks are not available for the 'SessionStart' hook event (no MCP client context)
, or the same message naming
Setup
. When
SessionStart
fires again later in the session, after
/clear
or a compaction, its
mcp_tool
hooks run. For anything the session needs at launch, use a
type: "command"
hook on
SessionStart
instead.
​
Prompt and agent hook fields
In addition to the
common fields
, prompt and agent hooks accept these fields:
Field
Required
Description
prompt
yes
Prompt text to send to the model. Use
$ARGUMENTS
as a placeholder for the hook input JSON. Escape with a backslash to include literal text:
\$1.00
renders as
$1.00
model
no
Model to use for evaluation. Defaults to the model Claude Code uses for
background functionality
​
Reference scripts by path
Use these placeholders to reference hook scripts relative to the project or plugin root, regardless of the working directory when the hook runs:
${CLAUDE_PROJECT_DIR}
: the project root where the session started. Claude Code also sets this variable in the environment of
stdio MCP servers
and plugin LSP servers.
${CLAUDE_PLUGIN_ROOT}
: the plugin’s installation directory, for scripts bundled with a
plugin
. See
plugin environment variables
for how the path behaves across updates.
${CLAUDE_PLUGIN_DATA}
: the plugin’s
persistent data directory
, for dependencies and state that should survive plugin updates.
Worktrees are different.
If Claude enters a
worktree
during the session, Claude Code keeps
${CLAUDE_PROJECT_DIR}
where it was and passes the worktree path to your hooks a different way:
${CLAUDE_PROJECT_DIR}
stays put
: it still points at the project root where the session started, so a command such as
${CLAUDE_PROJECT_DIR}/.claude/hooks/check-style.sh
still runs the script in the main checkout.
cwd
follows Claude
: the
cwd
field in the hook’s
input JSON
is the worktree root after Claude enters a worktree, and the new directory after Claude runs
cd
. Read it when a hook needs to know which directory Claude is working in.
For a worktree session that you start from the desktop app, see
What worktrees share with the main checkout
for where
${CLAUDE_PROJECT_DIR}
points.
Prefer
exec form
for any hook that references a path placeholder. In shell form, wrap each placeholder in double quotes.
Project scripts
Plugin scripts
This example uses
${CLAUDE_PROJECT_DIR}
to run a style checker from the project’s
.claude/hooks/
directory after any
Write
or
Edit
tool call:
{
"hooks"
: {
"PostToolUse"
: [
{
"matcher"
:
"Write|Edit"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"${CLAUDE_PROJECT_DIR}/.claude/hooks/check-style.sh"
,
"args"
: []
}
]
}
]
}
}
Define plugin hooks in
hooks/hooks.json
with an optional top-level
description
field. When a plugin is enabled, its hooks merge with your user and project hooks.
This example runs a formatting script bundled with the plugin:
{
"description"
:
"Automatic code formatting"
,
"hooks"
: {
"PostToolUse"
: [
{
"matcher"
:
"Write|Edit"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"${CLAUDE_PLUGIN_ROOT}/scripts/format.sh"
,
"args"
: [],
"timeout"
:
30
}
]
}
]
}
}
See the
plugin components reference
for details on creating plugin hooks.
​
Hooks in skills and agents
In addition to settings files and plugins, hooks can be defined directly in
skills
and
subagents
using frontmatter, in the same configuration format as settings-based hooks. How long Claude Code keeps them registered depends on the component:
Subagent hooks
: Claude Code runs them only while that subagent is running and removes them when it finishes. Claude Code converts a
Stop
hook here to
SubagentStop
, the event it fires when a subagent completes.
Skill hooks
: Claude Code registers them when you or Claude invoke the skill and keeps running them for the rest of the session, on turns after the skill’s own turn as well. To have Claude Code remove a hook after its first successful run instead, set
once: true
on it.
This skill defines a
PreToolUse
hook that runs a security validation script before each
Bash
command:
---
name
:
secure-operations
description
:
Perform operations with security checks
hooks
:
PreToolUse
:
-
matcher
:
"Bash"
hooks
:
-
type
:
command
command
:
"./scripts/security-check.sh"
---
Subagents use the same format in their YAML frontmatter.
Frontmatter hooks in a project skill follow the same
workspace trust rule as hooks in settings files
. Claude Code registers them when you or Claude invoke the skill, including in a
-p
run in a folder you haven’t trusted.
Frontmatter hooks in a project subagent run only after you accept the
workspace trust dialog
for the folder the agent file came from. A
-p
session doesn’t count as accepting it.
What runs before you trust a folder
compares this with the settings-file rule, and the subagents page lists
which scopes are exempt
.
​
Limits on skill hooks
When a skill’s frontmatter hooks don’t fire after you or Claude invoke the skill, run
/hooks
in that session. If it lists them, see
Hook not firing
. If it lists none of them, the skill may be under a plugin-only lock or past a hook limit, and runs without any of its frontmatter hooks. Check for each case:
Plugin-only lock
: your organization’s administrator can lock hooks to plugins and managed settings with the
strictPluginOnlyCustomization
managed setting. A skill keeps its frontmatter hooks under that lock only if it’s a plugin skill, a
bundled skill
, or a skill in the
managed settings directory
. The hooks in your own settings files don’t run either.
Check
: type
/status
in a Claude Code session. If the
Setting sources
line
includes
Enterprise managed settings
, ask your administrator whether
strictPluginOnlyCustomization
locks hooks.
Fix
: move the skill into a
plugin
, because plugin skills keep their frontmatter hooks. List the plugin in a
marketplace
, then install it from there. If Claude Code refuses the marketplace with
is blocked by enterprise policy
, ask your administrator to allow that marketplace.
Hook limit
: in Claude Code v2.1.304 or later, each source of skills has its own limit per session. Your project, your personal skills folder, and each plugin count as separate sources. The skills from one source can register at most 1,024 hooks. Those hooks’ matchers can total at most 16,384 characters. A matcher with several hooks under it counts once for each hook.
Check
: repeat the session where the hook didn’t fire, with debug logging on:
Start a new session from your shell with
claude --debug
. If you don’t start sessions from a shell, type
/debug
first in the new session instead.
Invoke the same skills in the same order, including the ones Claude invoked, because both totals build up skill by skill. Ask Claude to invoke any skill you can’t type as a command.
Search the
debug log
for
registers none of its hooks
. A line containing that text names the skill that went past the limit.
Fix
: declare fewer hooks or shorter matchers in that skill or in the other skills from its source, then start a new session. If those skills aren’t yours to edit, ask their author for that change. Until then, start a new session and invoke the skill you need before any other skill from its source.
If neither case is yours, check for
frontmatter that didn’t parse
.
​
The
/hooks
menu
Type
/hooks
in Claude Code to open a read-only browser for your configured hooks. The list labels each hook with where it comes from, such as user settings, project settings, local settings, a plugin, or the current session.
Select a hook to see the full text of what it runs and where it’s defined, such as the path of its settings file or the name of its plugin.
To browse all hook events, including ones with no hooks configured, select
All events
at the end of the list.
​
Disable or remove hooks
To remove a hook defined in a settings file, delete its entry from that file.
To temporarily disable all hooks without removing them, set
"disableAllHooks": true
in your settings file. Claude Code reads the value left after
settings precedence
applies, so a
"disableAllHooks": false
in a project’s
.claude/settings.json
overrides a
true
in your user settings. To turn hooks off for one run whatever the project’s settings say, pass
--settings '{"disableAllHooks": true}'
, which takes precedence over project and local settings. There is no way to disable an individual hook while keeping it in the configuration.
The
disableAllHooks
setting respects the managed settings hierarchy. If an administrator has configured hooks through managed policy settings,
disableAllHooks
set in user, project, or local settings can’t disable those managed hooks. Only
disableAllHooks
set at the managed settings level can disable managed hooks. For the full reach of each level, see
disableAllHooks
.
Direct edits to hooks in settings files are normally picked up automatically by the file watcher.
​
Hook input and output
Command hooks receive JSON data via stdin and communicate results through exit codes, stdout, and stderr. HTTP hooks receive the same JSON as the POST request body and communicate results through the HTTP response body. This section covers fields and behavior common to all events. Each event’s section under
Hook events
includes its specific input schema and decision control options.
On macOS and Linux, command hooks run in their own session without a controlling terminal. The hook process and any child processes can’t open
/dev/tty
or send escape sequences directly to the Claude Code interface. Windows has no
/dev/tty
.
To surface a message to the user on any platform, return
systemMessage
in JSON output. Some events discard it or deliver it elsewhere, and each
event’s section
says so. To trigger a desktop notification, set a window title, or ring the bell, return
terminalSequence
instead.
​
Common input fields
Hook events receive these fields as JSON, in addition to event-specific fields documented in each
hook event
section. For command hooks, this JSON arrives via stdin. For HTTP hooks, it arrives as the POST request body.
Field
Description
session_id
Current session identifier
prompt_id
UUID identifying the user prompt currently being processed. Matches the
prompt.id
attribute on OpenTelemetry events
, so you can correlate hook output with telemetry for a single prompt. Absent until the first user input
transcript_path
Path to conversation JSON. The transcript file is written asynchronously and may lag the in-memory conversation, so it may not yet include the current turn’s most recent messages when a hook fires. Hooks that need the final assistant text of the current turn should use
last_assistant_message
on
Stop
and
SubagentStop
instead of reading the transcript
cwd
Current working directory when the hook is invoked
scratchpad_dir
Path to the session’s
scratchpad directory
, where Claude keeps temporary working files. Absent when the session has no scratchpad or the temp directory is unavailable. Requires Claude Code v2.1.257 or later
permission_mode
Current
permission mode
:
"default"
,
"plan"
,
"acceptEdits"
,
"auto"
,
"dontAsk"
, or
"bypassPermissions"
. The mode labeled
Manual
arrives as
"default"
, never as
"manual"
, so scripts that match
"default"
keep working. Not all events receive this field. Check the JSON example in each
hook event
section
effort
Object whose
level
is the
effort level
setting when the hook runs, including a skill’s, subagent’s, or
ultrathink
level:
"low"
,
"medium"
,
"high"
,
"xhigh"
, or
"max"
. Present for
PreToolUse
,
PostToolUse
,
Stop
,
SubagentStop
, and other events with a tool-use context, on models with effort. If the model doesn’t support your level,
level
is the level that ran. A level you changed can show here before it
starts
.
$CLAUDE_EFFORT
holds the same level.
hook_event_name
Name of the event that fired
agent_id
and
agent_type
tell your script which agent a hook fired in, such as a subagent, an
in-process teammate
, or the agent you chose with
--agent
:
Field
Description
agent_id
Unique identifier for the subagent or in-process teammate the hook fires in.
agent_type
Agent name (for example,
"Explore"
or
"security-reviewer"
). Present when the session uses
--agent
or the hook fires inside a subagent. For subagents, the subagent’s type takes precedence over the session’s
--agent
value. See
SubagentStart
for the values custom and plugin subagents report and how to write a matcher against a plugin-scoped name.
Only
SessionStart
hooks can receive a
model
field, and Claude Code doesn’t always include it.
PreModelSwitch
and
PostModelSwitch
hooks receive
from_model
and
to_model
instead, so use a PostModelSwitch hook to follow the model as it changes during a session.
There is no
$CLAUDE_MODEL
environment variable. The hook can read
$ANTHROPIC_MODEL
if you set it in your shell, but that value doesn’t change when you switch models with
/model
during a session.
A hook process inherits the parent environment, apart from the
OTEL_*
exporter variables that Claude Code
removes from every subprocess it spawns
and, when
CLAUDE_CODE_SUBPROCESS_ENV_SCRUB
is set to
1
, the variables it strips. In a session that
gets the HIPAA configuration
, Claude Code also
removes Anthropic credentials
from the hook’s environment.
For example, a
PreToolUse
hook for a Bash command receives this on stdin:
{
"session_id"
:
"abc123"
,
"prompt_id"
:
"550e8400-e29b-41d4-a716-446655440000"
,
"transcript_path"
:
"/home/user/.claude/projects/.../transcript.jsonl"
,
"cwd"
:
"/home/user/my-project"
,
"scratchpad_dir"
:
"/tmp/claude-1000/-home-user-my-project/abc123/scratchpad"
,
"permission_mode"
:
"default"
,
"hook_event_name"
:
"PreToolUse"
,
"tool_name"
:
"Bash"
,
"tool_input"
: {
"command"
:
"npm test"
,
"description"
:
"Run test suite"
,
"timeout"
:
120000
,
"run_in_background"
:
false
},
"tool_use_id"
:
"toolu_01ABC123..."
}
The
tool_name
,
tool_input
, and
tool_use_id
fields are event-specific. Each
hook event
section documents the additional fields for that event.
​
Exit code output
When your hook’s run finishes, Claude Code uses its exit code to decide whether to continue with the action that triggered it, such as a tool call or a prompt:
Success
: your hook exits 0. Claude Code applies any
JSON output
fields your hook printed, and the action goes ahead unless those fields block or deny it.
Hooks that start a background process
covers the exception.
Blocking error
: your hook exits 2. On
events that can block
, Claude Code stops the action.
Non-blocking error
: your hook exits with any other code, or fails in some other way, such as not starting or printing invalid JSON. The action goes ahead, except for hooks
whose failure blocks the action
, for example a hook with
onFailure
set to
"block"
. On events such as
PreToolUse
, you see a
<hook name> hook error
notice in the transcript.
What your hook prints to stdout can change the outcome. For example, when a
PreToolUse
hook exits 1 but prints JSON that passes validation, that JSON can still decide what happens. To find your hook’s outcome on an event such as
PreToolUse
, match what it printed to stdout in the first column with its exit code along the top:
Stdout
Exit 0
Exit 2
Any other exit code
JSON object that passes
schema validation
Success. The fields apply
Blocking error. Claude Code still reads the fields, but they can’t override the block
Success. Claude Code ignores the exit code, and the fields alone decide. For hooks
whose failure blocks the action
, the run counts as a failure instead
JSON that
can’t be parsed
or fails schema validation
Non-blocking error. The notice carries the parse or validation message
Blocking error. Your stderr is the reason
Non-blocking error. The notice carries the parse or validation message
Plain text
, or nothing
Success
Blocking error. Your stderr is the reason
Non-blocking error. The notice carries the first line of your stderr
Some events have their own rules:
WorktreeCreate
: any non-zero exit code makes worktree creation fail, whatever your JSON says.
WorktreeRemove
: any non-zero exit code makes worktree removal fail if the directory still exists afterward.
Stop
,
SubagentStop
,
TaskCompleted
, and a plugin’s
UserPromptSubmit
hook
: when your hook exits 2 with nothing on stdout and its stderr says a file is missing, such as
No such file or directory
, Claude Code treats the run as a non-blocking error.
Elicitation
and
ElicitationResult
: Claude Code applies your
hookSpecificOutput
when your hook exits 0, and ignores it on any other exit code.
Events that discard hook output, such as
StopFailure
: Claude Code ignores your JSON on any exit code, apart from side-effect fields like
terminalSequence
, which still fire.
To check what exit code 2 does on your event, see
Exit code 2 behavior per event
. To check which decision fields it honors, see
Decision control
.
​
Exit code 0
Exit 0 means success, and is the intended exit code when you print JSON for structured control. When your hook exits

## Source (permissions): https://docs.claude.com/en/docs/claude-code/permissions

Configure permissions - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
Claude Code supports fine-grained permissions so that you can specify exactly what the agent is allowed to do and what it can’t. You can check permission settings into version control to share them with every developer in your organization, and each developer can customize their own.
​
Permission system
Claude Code uses a tiered permission system to balance power and safety. The table shows, for each tool type, whether Manual mode asks before the action runs. The other
permission modes
change which of these ask you; in auto mode a classifier reviews actions instead of you, and
how the classifier evaluates actions
lists which ones it sees.
Tool type
Example
Approval required
”Yes, and don’t ask again” behavior
Read-only
File reads, Grep
No, within the
working directory and additional directories
N/A
Bash commands
Shell execution
Yes, except a built-in set of
read-only commands
Permanently per repository and command
File modification
Edit/write files
Yes
Until session end
Web fetch
WebFetch
Yes, except a built-in set of
preapproved documentation domains
Permanently per repository and domain
Web search
WebSearch
Yes
Permanently per repository
A permission prompt shows what Claude is about to do, followed by your options. This example is the prompt for a Bash command, from a session in Manual mode:
The third option,
Yes, and switch to auto mode
,
doesn’t appear on every prompt
.
When you choose “Yes, and don’t ask again” and the approval saves permanently, such as for a Bash command or a WebFetch domain, Claude Code saves the rule to
.claude/settings.local.json
at the root of the git repository, resolved through
worktrees
to the main checkout. The rule applies to future sessions anywhere in that repository, including sessions started in subdirectories and in worktrees. A file-modification approval isn’t saved to the file: as the table shows, it lasts until the session ends. In some cases, such as outside a git repository or on Windows, Claude Code doesn’t use the repository root;
Where Claude Code looks for each file
lists those cases and where it saves the rule instead.
Sometimes a permission prompt offers only a one-time approval, with no “don’t ask again” option and no option to allow the action for the rest of the session. Claude Code offers those options only when the prompt can show you everything they would allow, so a rule you save from a prompt covers only what its option named. When a prompt offers only the one-time approval, approve the action once, or add the rule yourself in
/permissions
. To stop the prompts for a command that starts with an exec wrapper such as
watch
, or for a
find
command with an action such as
-delete
, see
Exec wrappers and
find
actions
.
​
Add a comment when you answer a permission prompt
You can attach a note to Claude when you approve or deny a single action. On most permission prompts, including Bash, PowerShell, file, and MCP tool prompts, move to
Yes
or
No
and press
Tab
to open a comment field on that option. WebFetch and browser prompts don’t offer the field. The options that allow the action for the rest of the session or save a rule don’t take one either.
With the field open, type the comment and then press one of these keys:
Enter
: submits your answer with the comment attached. If you leave the field empty, Claude Code submits the answer without a comment.
Tab
: closes the field without answering. Claude Code keeps the text you typed and still sends it if you answer with that option.
Shift+Tab
: on a file prompt, such as an Edit or Write prompt, closes the field the same as
Tab
. Before v2.1.235, pressing
Shift+Tab
inside the field instead selected the option that allows the action for the rest of the session, so Claude Code approved the action for the rest of the session and discarded the comment.
Claude Code delivers the comment differently depending on how you answered:
Yes
: Claude Code runs the action, then sends your comment to Claude after the result.
No
: Claude Code sends your comment to Claude as the reason for the denial, and Claude continues working. If you select
No
without a comment on a prompt from the main conversation, Claude Code stops the turn.
​
Manage permissions
You can view and manage Claude Code’s tool permissions with
/permissions
. The dialog lists all permission rules and the
settings.json
file each rule comes from. You can open the dialog while Claude is working: when you add or remove a rule, Claude Code applies the change starting with Claude’s next tool call in the same turn. Before v2.1.234, Claude Code queued the command until the turn finished.
Allow
rules let Claude Code use the specified tool without manual approval.
Ask
rules prompt for confirmation whenever Claude Code tries to use the specified tool.
Deny
rules prevent Claude Code from using the specified tool.
Rules are evaluated in order: deny, then ask, then allow. The first match in that order determines the outcome, and rule specificity doesn’t change the order.
A broad deny rule like
Bash(aws *)
blocks every matching call, including calls that also match a narrower allow rule like
Bash(aws s3 ls)
. An allow rule can’t carve an exception out of a deny rule. The same precedence applies between ask and allow: a matching ask rule prompts even when a more specific allow rule also matches the same call.
Deny rules behave differently depending on whether they name a tool or scope a pattern within one. A bare tool name like
Bash
removes the tool from Claude’s context entirely, so Claude never sees it. If you add such a rule mid-session, Claude can’t call the tool from its next tool call on;
Denying an entire tool
covers what happens to a definition Claude has already seen. A scoped rule like
Bash(rm *)
leaves the tool available and blocks matching calls when Claude attempts them.
Bare-name removal applies to every tool except
EndConversation
: a deny rule can’t remove it while any other tool remains, and an ask rule never prompts for it.
Permission rules are enforced by Claude Code, not by the model. Instructions in your prompt or
CLAUDE.md
shape what Claude tries to do, but they don’t change what Claude Code allows. To grant or revoke access, use
/permissions
, the rules described here, a
permission mode
, or a
PreToolUse hook
.
When
auto mode
is available to your session, the dialog also includes the
auto mode classifier rules
. Select the
Auto mode
tab to view them.
​
Permission modes
Claude Code supports several permission modes that control how it approves tool calls. See
Permission modes
for when to use each one. To change the mode sessions start in, set
defaultMode
in your
settings files
.
Which mode a session starts in
covers the built-in default for each plan and what the VS Code extension reads.
Mode
Description
default
Prompts for permission on first use of each tool. Labeled Manual in the CLI, the VS Code and JetBrains extensions, and the desktop app, and Claude Code accepts
manual
as an alias
acceptEdits
Automatically accepts file edits and common filesystem commands such as
mkdir
,
touch
,
mv
, and
cp
for paths in the working directory or
additionalDirectories
plan
Claude reads files and runs read-only shell commands to explore but doesn’t edit your source files; with
auto mode
available, classifier-approved commands also run. Labeled Plan in the CLI and the VS Code extension
auto
Runs without routine prompts; before actions such as shell commands and network requests run, a background
classifier
checks that they align with your request
dontAsk
Auto-denies every call that would otherwise prompt, though a
mod
you installed can still approve some of those calls. File reads in your working directories and other actions that need no approval still run, as do tools pre-approved via
/permissions
or
permissions.allow
rules.
AskUserQuestion
, MCP tools marked
requiresUserInteraction
,
reads from network paths
, and connector tools
your organization set to
ask
in sessions where that setting reaches Claude Code are denied even if you’ve allowed them
bypassPermissions
Skips permission prompts, except for the
actions no mode auto-approves
In
bypassPermissions
mode, Claude Code skips permission prompts, including for writes to
protected paths
such as
.git
and
.claude
. The
cross-session messaging safeguards
still apply. Only use this mode in isolated environments like containers or VMs where Claude Code can’t cause damage.
To prevent
bypassPermissions
or
auto
mode from being used, set
permissions.disableBypassPermissionsMode
or
permissions.disableAutoMode
to
"disable"
in any
settings file
. These are most useful in
managed settings
where they can’t be overridden.
​
Permission rule syntax
Permission rules follow the format
Tool
or
Tool(specifier)
. Parentheses inside the specifier are literal, so a command or path that contains them needs no escaping.
​
Match all uses of a tool
To match all uses of a tool, use only the tool name without parentheses:
Rule
Effect
Bash
Matches all Bash commands
WebFetch
Matches all web fetch requests
Read
Matches all file reads
Bash(*)
is equivalent to
Bash
and matches all Bash commands. As a deny rule, both forms remove the tool from Claude’s context.
The label shown for a tool in the transcript and permission dialog can differ from its canonical name. For example, the tool labeled
Stop Task
in the transcript has the canonical name
TaskStop
. Permission rules and
hook matchers
don’t match the label, so a rule written as
Stop Task
doesn’t match. For deny and ask rules, a
startup warning
says so. Use the canonical names listed in the
tools reference
.
​
Use specifiers for fine-grained control
Add a specifier in parentheses to match specific tool uses:
Rule
Effect
Bash(npm run build)
Matches the exact command
npm run build
Read(./.env)
Matches reading the
.env
file in the current directory
WebFetch(domain:example.com)
Matches fetch requests to example.com
​
Match by input parameter
Deny and ask rules can match a top-level input parameter on any built-in tool with
Tool(param:value)
.
To match a parameter on an MCP tool, pass a deny rule with
--disallowedTools
. When Claude Code loads a settings file, it skips any
mcp__
rule that has parentheses. Claude Code lists the skipped rule in the invalid-settings dialog when an interactive session starts, and in
claude doctor
output.
A parameter rule matches when Claude calls the tool with that parameter set to that exact value. An allow rule for one parameter value wouldn’t establish that the call is safe overall, so allow rules continue to use each tool’s own specifier syntax. This works for any scalar parameter the tool accepts:
Rule
Matches
Agent(model:opus)
Agent calls that request the Opus model tier
Agent(isolation:worktree)
Agent calls that request a git worktree
Bash(run_in_background:true)
Bash calls that run in the background
Parameter matching follows these rules:
The parameter name must be a direct field of the tool’s input, such as
model
on the Agent tool. Fields nested inside an object or array are not matchable
Each rule names one parameter. To gate on both
model
and
isolation
, write two rules,
Agent(model:opus)
and
Agent(isolation:worktree)
, rather than combining them in one rule
The value supports
*
as a wildcard that matches any sequence of characters, so
Agent(isolation:*)
matches any explicit isolation value. Without
*
the match is exact
A parameter the model omits is never matched, so
Agent(model:*)
doesn’t match a call that leaves
model
unset
The value is compared against the literal input Claude sends, before any normalization.
Agent(model:opus)
matches the alias
opus
but not a full model ID
A
Skill(skill:<name>)
deny rule instead
matches the skill under any of its names
, such as its alias or display name
Run with
--verbose
to see the exact parameter names and values in each tool call
Whitespace around the colon is ignored
You can’t match a tool’s primary content field this way:
command
for Bash and PowerShell,
file_path
for Read, Edit, and Write,
path
for Grep and Glob,
notebook_path
for NotebookEdit, and
url
for WebFetch. A rule like
Bash(command:rm *)
would be bypassable by a compound command, so Claude Code ignores it and emits a startup warning. Use
Bash(rm *)
,
Read(./path)
, or
WebFetch(domain:host)
instead.
​
Wildcard patterns
A
*
in a Bash rule matches any text, including spaces, so one rule covers a family of commands. A rule with no
*
matches one exact command.
Put the
*
after the subcommand. In
git log --oneline main
,
git
is the program and
log
is the subcommand, the word that determines what the program does. Claude Code matches everything before the first
*
as written, so those words are what limit the rule:
Bash(git log *)
allows only
git log
commands, and
Bash(git *)
allows every git command. Claude Code
warns at startup
about an allow rule with a
*
before the subcommand, such as
Bash(git * main)
.
Write the command you want Claude to run without asking, and replace the parts that vary with
*
. With this configuration, Claude Code runs npm scripts and git commits without asking and refuses commands that begin with
git push
. A push written another way, such as
git -C . push
, isn’t matched; see
what a Bash rule doesn’t match
.
{
"permissions"
: {
"allow"
: [
"Bash(npm run *)"
,
"Bash(git commit *)"
],
"deny"
: [
"Bash(git push *)"
]
}
}
A
*
can go anywhere in the rule: at the start, in the middle, or at the end. Each row shows a rule, commands it matches, and nearby commands it doesn’t match:
You write
Matches
Doesn’t match
Bash(npm run build)
npm run build
npm run build --watch
Bash(npm run *)
npm run build
,
npm run test --watch
,
npm run
npm install
Bash(git log * main)
git log --oneline main
,
git log -5 main
,
git log --output=<file> main
git log main
,
git push origin main
Bash(git * main)
git merge main
,
git push origin main
,
git -c core.fsmonitor=<script> diff main
git log
Bash(* --version)
node --version
,
bash -c 'echo hi' --version
node -v
Bash(ls *)
ls -la
,
ls
lsof
Bash(ls*)
ls -la
,
lsof
Bash(* --help *)
npm --help x
npm --help
Three matching rules produce those rows:
The
*
stands in for whatever text is in its place.
In
Bash(git * main)
, it stands in for the subcommand, so Claude Code matches every git subcommand and every option before it. That includes
-c
, which makes git run a program you name. In
Bash(* --version)
, the
*
stands in for the program, so any program matches.
A
*
at the end, with a space before it, also matches the bare command.
Bash(ls *)
matches
ls
, and
Bash(git log *)
matches
git log
. That holds only when the trailing
*
is the rule’s only wildcard:
Bash(* --help *)
matches
npm --help x
but not
npm --help
.
The space before a trailing
*
is part of the rule.
Bash(ls *)
requires a space after
ls
, so
lsof
doesn’t match.
Bash(ls*)
has no space, so it matches
lsof
too.
The
:*
suffix is an equivalent way to write a trailing wildcard, so
Bash(ls:*)
matches the same commands as
Bash(ls *)
.
The permission dialog writes the space-separated form when you select “Yes, and don’t ask again” for a command prefix. The
:*
form is only recognized at the end of a pattern. In a pattern like
Bash(git:* push)
, the colon is treated as a literal character and won’t match git commands.
​
Tool name wildcards
Deny and ask rules also accept glob patterns in the tool-name position. The pattern must match the full tool name:
"*"
matches every tool, and
"mcp__*"
matches every MCP tool across all servers. A tool matched by a bare-name glob deny rule is removed from Claude’s context, the same as a bare tool name, including the
EndConversation
exception: a glob deny can’t remove it while any other tool remains, and a glob ask never prompts for it. This configuration denies every MCP tool:
{
"permissions"
: {
"deny"
: [
"mcp__*"
]
}
}
Allow rules accept tool-name globs only after a literal
mcp__<server>__
prefix. The server segment must be glob-free so the rule names a specific server you configured.
mcp__puppeteer__*
matches every tool from the
puppeteer
server, and
mcp__github__get_*
matches its
get_
tools. An unanchored allow glob such as
"*"
,
"B*"
, or
"mcp__*"
is skipped and doesn’t auto-approve anything.
A deny or ask rule whose tool name matches no known tool produces a
startup warning
to catch typos. Tool names containing
_
or
*
are exempt from the check, and so are the names of tools Claude Code has removed, such as
TaskOutput
.
​
Tool-specific permission rules
​
Bash
Bash rules match the whole command text, with
*
standing in for any text.
Wildcard patterns
shows which commands each rule shape matches and where to put the
*
. The rest of this section covers how Claude Code matches compound commands and wrappers, which wrappers and
find
actions a prefix rule can’t approve, what a rule doesn’t match, read-only commands, and redirections.
​
Compound commands
Claude Code is aware of shell operators, so a rule like
Bash(safe-cmd *)
won’t give it permission to run the command
safe-cmd && other-cmd
. The recognized command separators are
&&
,
||
,
;
,
|
,
|&
,
&
, and newlines. Every subcommand must be allowed for a compound command to run without a prompt, for example because the subcommand matches an allow rule or is a
read-only command
.
Deny and ask rules apply when any subcommand matches them, including a command nested inside a subshell, a command substitution, or a control-flow body such as a
for
loop. An ask rule like
Bash(git clean *)
still prompts you for
cd /tmp && git clean -f
or
echo "$(git clean -f)"
, even in
auto mode
.
When
&&
or
||
has nothing after it, such as in
npm test &&
, Claude Code treats the command as unparseable and doesn’t split it into subcommands for allow-rule matching, so a rule such as
Bash(npm *)
doesn’t approve it.
When you approve a compound command with “Yes, and don’t ask again”, Claude Code saves a separate rule for each subcommand that requires approval, rather than a single rule for the full compound string. For example, approving
git status && npm test
saves a rule for
npm test
, so future
npm test
invocations are recognized regardless of what precedes the
&&
. Subcommands like
cd
into a directory outside your working directories generate their own Read rule for that path. Up to 5 rules may be saved for a single compound command.
​
Wrappers
Before matching Bash rules, Claude Code strips a fixed set of wrappers, so a rule like
Bash(npm test *)
also matches
timeout 30 npm test
. The stripped wrappers are
timeout
,
time
,
nice
,
nohup
, and
stdbuf
, plus the shell builtins
command
and
builtin
, and zsh’s
noglob
. Each runs its argument as the actual command. Two related forms aren’t stripped: the query form
command -v
, which looks up a command rather than running one, and zsh’s
nocorrect
.
Claude Code also strips a leading assignment of certain known-safe environment variables, so
Bash(npm test *)
matches
NODE_ENV=test npm test
. An allow rule won’t match past an assignment of any other variable. A deny or ask rule matches past any leading assignment, so
Bash(rm *)
in deny still matches
FOO=bar rm -rf tmp/
.
Bare
xargs
is also stripped, so
Bash(grep *)
matches
xargs grep pattern
. Stripping applies only when
xargs
has no flags: an invocation like
xargs -n1 grep pattern
is matched as an
xargs
command, so rules written for the inner command do not cover it.
This wrapper list is built in and is not configurable. Development environment runners such as
direnv exec
,
devbox run
,
mise exec
,
npx
, and
docker exec
are not in the list. Because these tools execute their arguments as a command, a rule like
Bash(devbox run *)
matches whatever comes after
run
, including
devbox run rm -rf .
. To approve work inside an environment runner, write a specific rule that includes both the runner and the inner command, such as
Bash(devbox run npm test)
. Add one rule per inner command you want to allow.
​
Exec wrappers and
find
actions
A prefix rule like
Bash(watch *)
or
Bash(find *)
can’t auto-approve the following commands, so in Manual mode they prompt:
Exec wrappers
: such as
watch
,
setsid
,
ionice
, and
flock
find
: with an action that runs commands, deletes files, or writes files, such as
-exec
,
-delete
,
-rm
, or
-fprint
, or with
-files0-from
, which takes the paths to search from a file
To approve a specific invocation that has no
*
in it, write an exact-match rule for the full command string, such as
Bash(find build -type f -delete)
.
When the command has a
*
, as in
find . -name '*.tmp' -delete
, Claude Code reads the rule as a
wildcard pattern
, not an exact match, so the command still prompts. Approve it each time it prompts, or use a
PreToolUse hook
that returns
"allow"
for it.
​
What a Bash rule doesn’t match
A Bash rule matches the command text Claude writes, after Claude Code splits
compound commands
and strips
wrappers
. It doesn’t match the same program invoked in a different form, so a deny or ask rule covers the invocation Claude usually produces and isn’t a security boundary around the program. These rules in
deny
or
ask
stop the first form and not the others:
Rule
Stops
Doesn’t stop
Bash(curl *)
curl https://example.com
/usr/bin/curl https://example.com
,
sh -c 'curl https://example.com'
Bash(rm *)
rm -rf build/
/bin/rm -rf build/
,
bash -c 'rm -rf build/'
Bash(git push *)
git push origin main
git -C . push origin main
,
git -c push.default=current push origin main
,
git 'push' origin main
Your other rules and the permission mode decide the commands in the last column.
For filesystem and network enforcement that doesn’t depend on the command text, use
sandboxing
. To inspect the full command text with your own logic before it runs, use a
PreToolUse hook
.
​
Read-only commands
Claude Code recognizes a built-in set of Bash commands as read-only and runs them without a permission prompt in every mode, except as
permissions.blockReadsOutsideWorkingDirectories
changes for paths outside your working directories. The set includes
ls
,
cat
,
echo
,
pwd
,
head
,
tail
,
grep
,
find
,
wc
,
which
,
diff
,
stat
,
du
,
cd
, and read-only forms of
git
. The set is not configurable; to require a prompt for one of these commands, add an
ask
or
deny
rule for it. In auto mode, these commands can also wait for the classifier’s review; see
how the classifier evaluates actions
.
A redirect such as
ls > out.txt
adds a check on the target. See
Redirections
.
Unquoted glob patterns are permitted for commands whose every flag is read-only, so
ls *.ts
and
wc -l src/*.py
run without a prompt.
In Manual mode, commands from this set still prompt in these cases:
Unquoted globs for commands with write-capable flags
: commands with write-capable or exec-capable flags, such as
find
,
sort
,
sed
, and
git
, prompt when an unquoted glob is present, because the glob could expand to a flag like
-delete
.
docker
pointed at another daemon
: read-only forms of
docker
prompt when the command carries a flag that selects a different daemon, such as
-H
,
--context
, or Podman’s
--url
and
--connection
.
file
with path-opening flags
:
file
prompts when it passes
-m
/
--magic-file
or
-f
/
--files-from
, because those flags make
file
open the paths named in the flag’s value.
ps
that could print environment variables
:
ps
prompts when one of its arguments could act as the
e
option, such as in
ps auxe
or
ps aux -e
, because that option prints process environment variables.
ps aux
and
ps -ef
run without a prompt. The check on dashed forms such as
ps aux -e
requires Claude Code v2.1.290 or later.
Network paths on Windows
: a command whose arguments include a network (UNC) path, such as
\\server\share\file
, prompts because accessing a network path can send your Windows credentials to the host it names. The same check applies to
PowerShell tool
commands.
Writes to special shell variables
: a command that sets, unsets, or loops over certain special shell variables, such as
PATH
or
IFS
, prompts even when the rest of the command is read-only.
Commands the analysis can’t parse
: when Claude Code can’t fully parse a command, it asks for approval instead of treating the command as read-only. Commands longer than 10,000 characters always prompt because they exceed what the analysis parses.
A
cd
into a path inside your working directory or an
additional directory
is also read-only, and a compound command like
cd packages/api && ls
runs without a prompt when each part qualifies on its own. These combinations prompt even when each part is read-only:
cd
with
git
: prompts when the
cd
changes into a different directory, since running
git
in a new directory can execute that directory’s hooks. A
cd
whose target resolves to the current working directory is a no-op and doesn’t trigger the prompt.
cd
with a redirect
: prompts when Claude Code can’t determine which directory the redirect target resolves against after the
cd
runs. A command whose only redirect target is
/dev/null
, such as
cd app; grep -r pattern . 2>/dev/null
, doesn’t prompt, because
/dev/null
doesn’t depend on the working directory.
Bash permission patterns that try to constrain command arguments are fragile. For example,
Bash(curl http://github.com/ *)
intends to restrict curl to GitHub URLs, but won’t match variations like:
Options before URL:
curl -X GET http://github.com/...
Different protocol:
curl https://github.com/...
Redirects:
curl -L http://short.example.com/xyz
, which redirects to GitHub
Variables:
URL=http://github.com && curl $URL
For more reliable URL filtering, consider:
Restrict Bash network tools
: use deny rules to stop
curl
,
wget
, and similar commands, then use the WebFetch tool with
WebFetch(domain:github.com)
permission for allowed domains. A deny rule doesn’t match the same program by path or inside
sh -c
, so pair it with the
sandbox network allowlist
when the restriction must hold; see
what a Bash rule doesn’t match
Use PreToolUse hooks
: implement a hook that validates URLs in Bash commands and blocks disallowed domains
Add CLAUDE.md guidance
: describe your allowed curl patterns in
CLAUDE.md
. This shapes what Claude tries but doesn’t enforce a boundary, so pair it with one of the options above
Note that using WebFetch alone doesn’t prevent network access. If Bash is allowed, Claude can still use
curl
,
wget
, or other tools to reach any URL.
​
Redirections
When a command redirects output or input, Claude Code checks the redirect target against your file rules as if Claude wrote or read that file directly:
Output redirects
: for
> file
,
>> file
, or
2> file
, the check covers your
Edit
allow and deny rules,
protected paths
, and the
working directories
. A rule such as
Bash(git commit *)
allows the command, not the target. A target that starts with
~
or contains a glob character needs your approval.
Input redirects
: for
< file
, the check covers your
Read
allow and deny rules and the working directories. A target outside the working directories needs your approval unless an allow rule covers it. A target that contains a glob pattern, or a relative path that follows a
cd
in the same command, needs your approval even when an allow rule covers it. Claude Code checks input targets in v2.1.257 and later.
Targets with no file behind them aren’t checked:
/dev/null
, file-descriptor forms such as
2>&1
and
<&3
, and here-docs and here-strings.
Claude Code also checks the files a
tee
command writes, including in a pipeline such as
make | tee build.log
. The check covers your
Edit
allow and deny rules,
protected paths
, and the
working directories
. An allow rule such as
Bash(tee *)
doesn’t cover a destination outside the working directories. Claude Code checks
tee
targets in v2.1.269 and later.
​
PowerShell
PowerShell permission rules use the same shape as
Bash rules
, and a bare
PowerShell
or
PowerShell(*)
matches every command. This configuration allows
Get-ChildItem
and
git commit
commands while blocking
Remove-Item
:
{
"permissions"
: {
"allow"
: [
"PowerShell(Get-ChildItem *)"
,
"PowerShell(git commit *)"
],
"deny"
: [
"PowerShell(Remove-Item *)"
]
}
}
Common aliases are canonicalized before matching. A rule written for the cmdlet name also matches those aliases, so
PowerShell(Get-ChildItem *)
matches
gci
,
ls
, and
dir
as well. Matching is case-insensitive.
Claude Code parses the PowerShell AST and checks each command in a compound command independently. Pipeline operators
|
, statement separators
;
, and on PowerShell 7+ the chain operators
&&
and
||
split a compound command into subcommands. Every subcommand must be allowed for the compound command to run without a prompt, for example by matching an allow rule.
​
Read and Edit
To block Claude’s file tools from reading a file or directory, add a
Read
deny rule for its path, such as
Read(./.env)
or
Read(./secrets/**)
;
Exclude sensitive files
has a paste-ready example. If your project has a
.claudeignore
file, it has no effect, so move its entries into
Read
deny rules.
​
What
Read
and
Edit
rules cover
Edit
rules apply to all built-in tools that edit files. Claude makes a best-effort attempt to apply
Read
rules to all built-in tools that read files like Grep and Glob, to
@file
mentions in your prompts, and to the selection and open-file context that a connected
IDE
shares with Claude.
A
Read(path)
deny rule also applies to image paths you paste into a prompt and directories you @-mention:
Image path
: when you paste an image’s path or drag an image file into your prompt in the terminal and the rule matches that path, Claude Code doesn’t attach the image. If the paste holds no other image, the path stays in your prompt as text.
Directory
: the
listing Claude receives
leaves out the file and directory names the rule matches.
Claude Code checks pasted image paths and directory listings in v2.1.290 and later.
A
Read
deny rule also blocks the
Edit and Write tools
on the same path, including creating a new file there. NotebookEdit isn’t covered, so add an
Edit
deny rule for paths no tool may change. For the Write tool, the check requires Claude Code v2.1.228 or later.
Read and Edit deny rules apply to Claude’s built-in file tools, to file commands Claude Code recognizes in Bash, such as
cat
,
head
,
tail
,
sed
, and
tee
, and to the targets of Bash
redirections
such as
> file
and
< file
. They don’t apply to a command that reads files without naming them, such as
grep -r pattern .
run from the directory that holds the file, or to arbitrary subprocesses that read or write files indirectly, like a Python or Node script that opens files itself. For OS-level enforcement that blocks all processes from accessing a path,
enable the sandbox
.
​
Write(path)
,
NotebookEdit(path)
, and
Glob(path)
rules never match
Claude Code checks file permissions against
Edit(path)
and
Read(path)
rules only. If you write a path rule for
Write
,
NotebookEdit
,
Glob
, or legacy
MultiEdit
, Claude Code accepts the rule but never matches a read or edit against it.
Use
Edit(docs/**)
in place of
Write(docs/**)
,
NotebookEdit(docs/**)
, or
MultiEdit(docs/**)
, and
Read(docs/**)
in place of
Glob(docs/**)
. To match every use of the Write, NotebookEdit, or Glob tool regardless of path, write only the tool name.
​
How path patterns match
Read and Edit rules both use
gitignore
pattern syntax with four distinct pattern types:
Pattern
Meaning
Example
Matches
//path
Absolute path from filesystem root
Read(//Users/alice/secrets/**)
/Users/alice/secrets/**
~/path
Path from home directory
Read(~/Documents/*.pdf)
/Users/alice/Documents/*.pdf
/path
Path relative to the settings source
Edit(/src/**/*.ts)
<primary working directory>/src/**/*.ts
in project settings
path
or
./path
Path relative to current directory
Read(*.env)
<cwd>/*.env
A pattern like
/Users/alice/file
isn’t an absolute path. The single leading slash anchors at the settings source, not the filesystem root. Use
//Users/alice/file
for absolute paths.
Where a pattern anchors
A
/path
pattern anchors at a directory associated with the settings source that defines it, so the same rule matches different locations depending on where you put it:
Rule defined in
/path
resolves to
Project settings at
.claude/settings.json
<primary working directory>/path
Local settings at
.claude/settings.local.json
<primary working directory>/path
User settings at
~/.claude/settings.json
~/.claude/path
A file passed with
--settings <file>
<directory of file>/path
CLI flags or session rules
<primary working directory>/path
A rule you add through
/permissions
follows the row for the settings file you save it to.
Local settings rules anchor at the session’s
primary working directory
, not at the repository root where Claude Code
stores the file
. In a session started at the repository root, the two directories are the same; in a
worktree
session, a shared rule such as
Edit(/src/**)
matches that worktree’s own
src/
directory.
A deny rule such as
Read(/secrets/**)
in user settings blocks
~/.claude/secrets/**
, not a
secrets
directory in your project. To write a rule in user settings that applies inside every project, use a
//
absolute path or a
~/
home-relative path instead.
On Windows, paths are normalized to POSIX form before matching.
C:\Users\alice
becomes
/c/Users/alice
, so use
//c/**/.env
to match
.env
files anywhere on that drive. To match across all drives, use
//**/.env
.
Examples:
Edit(/docs/**)
: edits in
<primary working directory>/docs/
, not
/docs/
or
<primary working directory>/.claude/docs/
Read(~/.zshrc)
: reads your home directory’s
.zshrc
Edit(//tmp/scratch.txt)
: edits the absolute path
/tmp/scratch.txt
Read(src/**)
: as an allow rule, reads from
<current-directory>/src/
only; as a deny or ask rule, matches a
src
directory at any depth under the current directory
How deep a pattern matches
A rule only matches files under its anchor; within that bound, matching depth depends on the pattern shape and, for single-segment directory patterns, the rule type, described below. Bare filenames follow gitignore semantics and match at any depth, so
Read(.env)
and
Read(**/.env)
are equivalent:
Deny rule
Blocks
Does not block
Read(.env)
or
Read(**/.env)
any
.env
at or under the current directory
.env
in a parent directory or another project
Read(//**/.env)
any
.env
anywhere on the filesystem
nothing; the rule is anchored at the filesystem root
A relative pattern with a single directory segment, such as
src/**
, matches at different depths depending on the rule type:
Allow rules
:
Edit(src/**)
matches only
<cwd>/src
and the files under it. To allow a directory name at any depth, write
Edit(**/src/**)
.
Deny and ask rules
:
Read(secrets/**)
matches a directory named
secrets
at any depth under the current directory, so the rule also applies to nested copies.
Every other pattern shape matches at the same depth in every rule type:
Edit(/src/**)
and
Edit(src/components/**)
match only at their anchored location, while
Edit(**/src/**)
matches at any depth.
The following example shows each pattern shape against a project with a top-level
src/
directory and a nested copy under
vendor/
:
<current-directory>/
├── src/
│   └── app.ts
└── vendor/
└── pkg/
└── src/
└── lib.js
Rule
Matches
src/app.ts
Matches
vendor/pkg/src/lib.js
Edit(src/**)
as an allow rule
Yes
No
Edit(src/**)
as a deny or ask rule
Yes
Yes
Edit(/src/**)
in any rule type
Yes
No
Edit(**/src/**)
in any rule type
Yes
Yes
In gitignore patterns,
*
matches within a single path segment and can appear at any position in the pattern, while
**
matches across directories.
​
Special characters and
!
negation
When you approve a file path with “Yes, and don’t ask again”, Claude Code escapes gitignore pattern characters in that path, such as
[
,
]
, and
*
, so the generated rule matches only the literal path you approved. Rules you write yourself aren’t escaped.
You don’t need to escape parentheses in a path, so
Edit(./Finance (2024)/**)
matches the
Finance (2024)
folder as spelled.
A deny or ask rule whose path isn’t usable as a gitignore pattern still guards that exact path. An allow rule with an unusable pattern doesn’t approve anything.
A deny or ask pattern that starts with
!
is a gitignore negation. It carves the paths it matches out of the
path
or
./path
rules listed before it. In one settings file’s
deny
list,
Read(*.env)
followed by
Read(!sample.env)
blocks every file whose name ends in
.env
at any depth, except files named
sample.env
. A
!
rule listed first carves nothing out.
The carve-out reaches only rules from the same source. A
Read(!.env)
in project settings or in
--disallowedTools
doesn’t cancel a
Read(./.env)
deny from managed settings or any other settings file.
Two limits narrow what a
!
pattern can carve out:
Claude Code reads a
!
pattern relative to the current directory even when
/
,
~/
, or
//
follows the
!
, so the pattern can’t reach a rule anchored with one of those prefixes.
Read(!~/notes/public/**)
carves nothing out of
Read(~/notes/**)
.
A carve-out can’t reopen a file inside a directory that a rule blocks as a whole. With
Read(secrets/**)
and
Read(!secrets/public/**)
, Claude Code still blocks
secrets/public
along with the rest of
secrets
.
​
Symlinks
When a file path Claude requests goes through a symlink, the permission check covers two paths: the one Claude requested and the file it resolves to. This applies to symbolic links on macOS, Linux, and Windows, and to directory junctions on Windows.
How rules match a symlinked path
Allow and deny rules treat the requested path and the file it resolves to differently:
Allow rules
: apply only when both the requested path and the file it resolves to match. A read through a symlink inside an allowed directory that points outside it doesn’t match the rule.
Deny rules
: apply when either the requested path or the file it resolves to matches. A symlink that points to a denied file is itself denied. For example, with
Read(./project/**)
allowed and
Read(~/.ssh/**)
denied, a symlink at
./project/key
pointing to
~/.ssh/id_rsa
is blocked: the target fails the allow rule and matches the deny rule.
On macOS and Linux, a deny or ask rule written through a symlinked directory with a
//
,
~/
, or
/
pattern also applies at the directory’s real location. For example, on macOS, where
/etc
resolves to
/private/etc
,
Read(//etc/**)
blocks
/private/etc/hosts
too. Before v2.1.268, a deny or ask rule written through a symlinked directory didn’t apply to a path given by its real location.
Grep and Glob search the directory the
path
argument resolves to. Claude Code applies
Read
deny rules to that directory.
Attachments through a symlink
A
Read
deny rule also covers these attachments, matching each one on either the named path or the file it resolves to. Claude Code leaves an attachment out of the conversation when a rule matches it:
@
-mentions
: a file or directory you mention in your prompt. A refused file leaves nothing in the conversation, and a
directory’s listing
leaves out the names a rule covers.
Pasted images
: an image whose path you paste or drag into the prompt in the terminal
Changed files
: a file Claude Code re-reads after it changes on disk
IDE context
: the selection and open-file context a connected IDE shares
With
permissions.blockReadsOutsideWorkingDirectories
on, or in a
--restricted
session, these attachments are also left out when they come from a path where that setting or flag refuses Claude’s file reads.
This line in place of a file you
@
-mentioned means Claude Code couldn’t work out where the path leads, for example because its symlinks form a loop:
Referenced <path> (not read: could not be examined)
Claude is told to read the path with its file tools instead, which can succeed when Claude Code only ran out of time to examine the path.
When the path’s symlinks don’t resolve, that read is
refused
too, so fix the link on disk or
@
-mention the file by a path that resolves.
Writes through a symlink
If the path Claude asks to edit or write is itself a symlink, the Edit and Write tools
refuse the write and direct Claude to the link’s target
.
A write can still pass through a symlink when a directory on the way to the file is a symlink, or when a Bash or PowerShell command does the writing. For those writes, what happens depends on where the file the write resolves to sits relative to your
working directories
and the
protected paths
:
Resolves outside the working directories
: when the requested path is inside your working directories and the file it resolves to isn’t, the write isn’t auto-approved in
acceptEdits
mode
. In
auto mode
, unless an allow rule approves the write, you’re prompted for it instead of the classifier deciding. The prompt names the path the write resolves to.
Resolves to a protected path that the requested path doesn’t name
: the
protected paths table
gives the outcome for each permission mode, except that where the table routes the write to the classifier, this write prompts you instead.
Paths that can’t be resolved or that change
When Claude Code can’t determine where a path leads on disk, for example because symlinks on it form a loop, the Read, Edit, and Write tools
refuse the operation
.
When a tool then opens the approved file, it
confirms that the path still resolves to the location the permission check approved
.
​
Network paths
When Claude’s file-reading tools, such as Read, Grep, and Glob, read from a network path, the read gets its own permission check. A network path is one that can reach another computer: on Windows, a UNC path such as
\\server\share\file
, and on macOS and Linux, a
/net
automount path such as
/net/fileserver/notes.txt
. Looking up such a path can contact the host it names, and on Windows that contact can send the host your credentials. Shell commands have their own check: in Manual mode, a read-only Bash or PowerShell command whose arguments include a UNC path
still prompts on Windows
.
In Claude Code v2.1.292 and later, each of these leaves the prompt in place:
Allow rules
: a rule doesn’t pre-approve the read, including a rule for the whole tool, such as
Read
PreToolUse hooks
: a
hook
that returns
"allow"
doesn’t skip the prompt
Auto mode
: the prompt comes to you, and the
classifier
doesn’t decide the read
In
dontAsk
mode, Claude Code denies the read instead of prompting. In
bypassPermissions
mode, and in interactive terminal sessions in plan mode with
bypass permissions
available, the read runs without this prompt.
To read files on a network share without this prompt, give the share a local path first:
Windows
: map the share to a drive letter and pass the drive with
--add-dir
when you launch Claude Code, as
Working directories
describes. For a share mapped to
Z:
, run
claude --add-dir Z:\
in PowerShell.
macOS and Linux
: mount the share at a local path, such as a directory under
/mnt
or
/Volumes
, and read the files from there, as
Working directory is a network path
describes
​
WebFetch
WebFetch rules use a
domain:
prefix and match against the hostname of the requested URL. Matching is case-insensitive, supports
*
wildcards, and strips a trailing
.
from both the rule and the hostname so
example.com.
and
example.com
are treated the same.
WebFetch(domain:example.com)
matches requests to
example.com
only. To also cover subdomains such as
api.example.com
, add a
WebFetch(domain:*.example.com)
rule
WebFetch(domain:*.example.com)
matches any subdomain at any depth, such as
api.example.com
or
a.b.example.com
, but not
example.com
itself
WebFetch(domain:*)
matches every domain. It isn’t the same as a bare
WebFetch
rule; see
Allow or deny every fetch
In any position other than a leading
*.
or a bare
*
, the wildcard matches only the text between two dots.
WebFetch(domain:example.*)
matches
example.org
, where
*
becomes
org
, but not
example.evil.com
, where
*
would have to become
evil.com
and cross a dot. This keeps a trailing wildcard from matching domains an attacker could register.
Wildcards in
WebFetch
rules require Claude Code v2.1.172 or later to match fetches.
​
Allow or deny every fetch
A bare
WebFetch
rule is the tool name with no
domain:
part, such as
"deny": ["WebFetch"]
. Both it and
WebFetch(domain:*)
cover every URL, but Claude Code applies them differently, and only the
domain:
form also adds its domain to the sandbox’s
allowed or denied domain list
. That section lists the wildcard forms the sandbox honors and the version that added bare
*
.
Each row shows what a rule does in the
allow
list and in the
deny
list:
Rule
In
allow
In
deny
WebFetch
Claude fetches without prompting you. Doesn’t change which hosts sandboxed commands can reach.
Claude Code removes the
WebFetch
tool, so Claude can’t fetch at all. Doesn’t change which hosts sandboxed commands can reach.
WebFetch(domain:*)
Claude fetches without prompting you, and sandboxed commands can reach any host.
Claude Code keeps the tool and refuses each fetch, and sandboxed commands can’t reach any host.
The two forms also differ on reads of
artifacts
, the pages the Artifact tool publishes on claude.ai. A bare
WebFetch
deny or ask rule doesn’t apply to those reads. A
domain:
rule covering
claude.ai
or the
*.claudeusercontent.com
content host, such as
WebFetch(domain:claude.ai)
or
WebFetch(domain:*)
, denies each read or prompts before it. An
Artifact
rule
does the same.
When a rule blocks a read, the denial names the rule. Before v2.1.268, a bare
WebFetch
deny rule blocked every artifact read, and a bare ask rule prompted before each one.
To let Claude fetch freely while keeping the sandbox allowlist as it is, use the bare form. This
settings.json
does that:
{
"permissions"
: {
"allow"
: [
"WebFetch"
]
}
}
When you ask Claude to fetch a page, it fetches without a prompt. When you ask it to run a
sandboxed
curl
against a host outside the sandbox allowlist, Claude Code still prompts you for that host, because the bare rule didn’t add the host to the allowlist.
In
auto mode
, Claude instead names the host in the command’s
per-command allowed domains
for the classifier to review.
​
MCP
To match every tool from an MCP server, write
mcp__<server>__*
. To match one tool, write its full name,
mcp__<server>__<tool>
.
mcp__puppeteer
matches any tool provided by the
puppeteer
server
mcp__puppeteer__*
uses wildcard syntax and also matches all tools from the
puppeteer
server
mcp__puppeteer__puppeteer_navigate
matches the
puppeteer_navigate
tool provided by the
puppeteer
server
For
<server>
, write the server’s name the way it appears in that server’s tool names. These examples show the rule to write for a name with special characters, a server from a plugin, and a name that contains
__
or ends in
_
:
Names with characters such as
.
or spaces
: those characters become
_
, so for a server you configured as
my.server
, write
mcp__my_server__*
Servers that a plugin provides
:
<server>
takes the
plugin-scoped form
, so for the
database-tools
server in a plugin named
my-plugin
, write
mcp__plugin_my-plugin_database-tools__*
A
<server>
that contains
__
or ends in
_
: write the wildcard form,
mcp__<server>__*
, with the whole name. For a server named
reports__v2
, write
mcp__reports__v2__*
. The bare
mcp__reports__v2
and the shorter
mcp__reports
don’t match its tools as allow rules, because Claude Code reads both as rules for a server named
reports
.
As a deny or ask rule, though, each of those two names also covers every tool of the
reports__v2
server. To cover a server named
reports
alone, write one rule per tool in the
mcp__reports__<tool>
form, or rename one of the servers.
If your organization has set a
claude.ai connector
tool to
ask
and that setting reaches Claude Code in your session, allow rules for that tool don’t take effect: Claude Code prompts on every call, even in
auto
and
bypassPermissions
modes. In
dontAsk
mode, which never prompts, Claude Code denies the call instead. Tools from connectors Claude Code fetches itself appear as
mcp__claude_ai_<server>__<tool>
.
In a
Cowork
session in the Claude Desktop app, Claude runs shell commands through Cowork’s
mcp__workspace__bash
tool rather than the built-in
Bash
tool, and Cowork likewise provides
mcp__workspace__web_fetch
for web fetches. Claude Code also applies deny rules that name the whole
Bash
or
WebFetch
tool to these Cowork tools, so a managed
Bash
deny rule stops Claude from running shell commands in Cowork. When Claude Code blocks such a call, the message names the Cowork tool:
Permission to use mcp__workspace__bash has been denied.
Allow rules don’t carry over: Claude Code never applies a
Bash
allow rule to
mcp__workspace__bash
.
​
Agent (subagents)
Use
Agent(AgentName)
rules to control which
subagents
Claude can use:
Agent(Explore)
matches the Explore subagent
Agent(Plan)
matches the Plan subagent
Agent(my-custom-agent)
matches a custom subagent named
my-custom-agent
Add these rules to the
deny
array in your settings or use the
--disallowedTools
CLI flag to disable specific agents. To disable the Explore agent:
{
"permissions"
: {
"deny"
: [
"Agent(Explore)"
]
}
}
​
Cd
Cd
rules control which directories the
/cd
command
can move the session to.
Cd
is not a model-invocable tool: Claude can’t call it, and the rules apply only when you run
/cd
yourself.
A bare
Cd
deny rule disables
/cd
entirely. A
Cd(<path-pattern>)
deny rule blocks matching targets. Deny rules check every spelling of the target, including each symlink hop it resolves through, so a rule written for one path also blocks targets that resolve to it.
Adding any
Cd
allow rule switches
/cd
to allowlist mode: the resolved target directory must match one of your allow rules, or
/cd
refuses. With no
Cd
rules configured,
/cd
keeps its default behavior and prompts you to trust an unfamiliar directory.
Path patterns share the
//
,
~/
, and
/
anchors from
Read a

## Source (agent-teams): https://docs.claude.com/en/docs/claude-code/agent-teams

Orchestrate teams of Claude Code sessions - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
Agent teams are experimental and disabled by default. Enable them by setting
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
in your
settings.json
or environment. Without that variable, no team is set up at session start, no team directories are written, and Claude does not spawn or propose teammates. Agent teams have
known limitations
around session resumption, task coordination, and shutdown behavior.
Agent teams let you coordinate multiple Claude Code instances working together. One session acts as the team lead, coordinating work, assigning tasks, and synthesizing results. Teammates work independently, each in its own context window, and communicate directly with each other. You can also talk to any teammate directly without going through the lead.
Before you set up a team, check whether a lighter option does the job.
Subagents
work within a single session, and with
cross-session messaging
Claude can pass findings between the sessions you run yourself.
​
When to use agent teams
Agent teams are most effective for tasks where parallel exploration adds real value. See
use case examples
for full scenarios. The strongest use cases are:
Research and review
: multiple teammates can investigate different aspects of a problem simultaneously, then share and challenge each other’s findings
New modules or features
: teammates can each own a separate piece without stepping on each other
Debugging with competing hypotheses
: teammates test different theories in parallel and converge on the answer faster
Cross-layer coordination
: changes that span frontend, backend, and tests, each owned by a different teammate
Agent teams add coordination overhead and use significantly more tokens than a single session. They work best when teammates can operate independently. For sequential tasks, same-file edits, or work with many dependencies, a single session or
subagents
are more effective.
​
Compare with subagents
Both agent teams and
subagents
let you parallelize work, but they operate differently. For separate sessions that pass messages to each other without a team, see
cross-session messaging
.
Subagents report results back to the main agent. In agent teams, teammates share a task list, claim work, and communicate directly with each other.
Subagents
Agent teams
Context
Own context window; results return to the caller
Own context window; fully independent
Communication
Return a result to the caller. Subagents that Claude
named
when it spawned them can also
message each other
Teammates message each other directly
Coordination
Main agent manages all work
Self-coordination through messages, plus a shared task list for
agents that have the Task tools
Best for
Focused tasks where only the result matters
Complex work requiring discussion and collaboration
Token cost
Lower: results summarized back to main context
Higher: each teammate is a separate Claude instance
Use subagents when you need quick, focused workers that report back. Use agent teams when teammates need to share findings, challenge each other, and coordinate on their own.
​
Enable agent teams
Agent teams are disabled by default. Enable them by setting the
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
environment variable to
1
, either in your shell environment or through
settings.json
:
settings.json
{
"env"
: {
"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"
:
"1"
}
}
Enabling agent teams also changes ordinary delegation. Claude may
name a subagent
on its own, and while agent teams are enabled, a subagent that Claude names launches as a teammate, so teams can form even when you didn’t ask for one. For more, see
How Claude starts agent teams
; to turn the behavior off, see
Claude spawns teammates instead of subagents
.
Spawning teammates also requires an interactive session. In
non-interactive mode
with the
-p
flag, including Agent SDK sessions, Claude doesn’t spawn teammates, and a subagent that Claude names runs as an ordinary
subagent
even with agent teams enabled.
​
Start your first agent team
After enabling agent teams, describe the task and the teammates you want in natural language. Claude spawns them and coordinates work based on your prompt.
This example works well because the three roles are independent and can explore the problem without waiting on each other:
I'm designing a CLI tool that helps developers track TODO comments across
their codebase. Spawn three teammates to explore this from different angles:
one on UX, one on technical architecture, one playing devil's advocate.
From there, Claude populates a
shared task list
in a
session that has the Task tools
, spawns teammates for each perspective, has them explore the problem, and synthesizes findings when finished.
Claude may sometimes use
subagents
instead of creating a team. Subagents appear in the same agent panel as teammates, so the panel alone doesn’t confirm a team formed. If Claude spawned subagents instead, ask again and explicitly request an agent team.
The lead’s terminal lists teammates in the agent panel below the prompt input. From the panel:
Up and down arrows
: select a teammate
Enter
: open the selected teammate’s transcript and message it directly
Escape
: clear the selection. While you’re viewing a teammate’s transcript, Escape interrupts that teammate’s current turn
An idle teammate’s row stays in the panel while any teammate or subagent is still working, so you can select it to review its transcript or send it more work. Once every agent in the panel is idle, idle rows hide after 30 seconds and reappear on the teammate’s next turn; the teammate stays running and addressable while hidden.
When more than three teammates are idle at once, the rows beyond the first three collapse into a single row that counts the collapsed teammates, such as
2 idle agents
when five are idle. Select it and press Enter to expand the collapsed rows, or press Esc to collapse them again. Working teammates, failed teammates, and the teammate you’re viewing always keep their own rows.
If you want each teammate in its own split pane, see
Choose a display mode
.
​
Control your agent team
Tell the lead what you want in natural language. It handles team coordination, task assignment, and delegation based on your instructions.
​
Choose a display mode
Agent teams support two display modes:
In-process
: all teammates run inside your main terminal. Use the up and down arrow keys in the agent panel to select a teammate, then press Enter to view it and type to message it directly. Works in any terminal, no extra setup required.
Split panes
: each teammate gets its own pane. You can see everyone’s output at once and click into a pane to interact directly. Requires tmux, or iTerm2.
tmux
has known limitations on certain operating systems and traditionally works best on macOS. Using
tmux -CC
in iTerm2 is the suggested entrypoint into
tmux
.
The default is
"in-process"
. Set
"auto"
to enable split panes when you’re already running inside a tmux session, or when your terminal is iTerm2 with the
it2
CLI installed, falling back to in-process otherwise. The
"tmux"
setting enables split-pane mode and auto-detects whether to use tmux or iTerm2 based on your terminal.
Set
"iterm2"
to use iTerm2 native split panes explicitly. This mode requires the
it2
CLI
and shows an error with the install command if
it2
is missing. The setup prompt that offers to install
it2
or switch to tmux appears under
"auto"
or
"tmux"
when your terminal is iTerm2 and tmux is available as a fallback.
To override the default, set
teammateMode
in
~/.claude/settings.json
:
{
"teammateMode"
:
"auto"
}
To set the mode for a single session, pass it as a flag:
claude
--teammate-mode
auto
The
--teammate-mode
flag is experimental and doesn’t appear in
claude --help
.
Split-pane mode requires either
tmux
or iTerm2 with the
it2
CLI
. To install manually:
tmux
: install through your system’s package manager. See the
tmux wiki
for platform-specific instructions.
iTerm2
: install the
it2
CLI
, then enable the Python API in
iTerm2 → Settings → General → Magic → Enable Python API
.
​
Specify teammates and models
Claude decides the number of teammates to spawn based on your task, or you can specify exactly what you want:
Spawn 4 teammates to refactor these modules in parallel. Use Sonnet for
each teammate.
Claude Code picks each teammate’s model from the first of these that applies:
The model your spawn prompt names for that teammate.
For a teammate spawned from a
subagent definition
, the definition’s
model
, where
inherit
selects the lead’s model.
CLAUDE_CODE_SUBAGENT_MODEL
, when it’s set to anything other than
inherit
.
The lead’s current model.
If an installed
mod
sets a model in its
agent.spawn
hook, Claude Code uses that model in place of the first source.
If you set
CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1
, the first two sources don’t apply. Claude Code picks every teammate’s model from
CLAUDE_CODE_SUBAGENT_MODEL
when it’s set to anything other than
inherit
, and from the lead’s current model otherwise. Requires Claude Code v2.1.257 or later.
Before v2.1.251,
CLAUDE_CODE_SUBAGENT_MODEL
came first in this order.
teammateDefaultModel
was removed in v2.1.234; Claude Code ignores a leftover value. Name the model in your prompt instead.
Claude Code checks the model it selects for a teammate against your organization’s
availableModels
allowlist. When the allowlist blocks a value, Claude Code substitutes another model:
Family alias such as
opus
: On the Anthropic API and Claude Platform on AWS, Claude Code runs the teammate on the newest version of that family the allowlist permits. On providers with provider-specific model IDs, where the
substitution doesn’t operate
, a blocked alias falls back like any other blocked value per the next bullet
Any other blocked value, including a family alias on providers where the substitution doesn’t operate, or one whose family has no permitted version
: Claude Code runs the teammate on the lead’s model instead. If you set
CLAUDE_CODE_SUBAGENT_MODEL
, Claude Code tries that model first, under these same rules
By default, teammates inherit the lead’s
effort level
. In split-pane mode this applies from v2.1.186; earlier versions did not pass the lead’s session effort to split-pane teammates.
​
Have teammates plan before implementing
For complex or risky tasks, you can have teammates plan before implementing. A teammate that Claude spawns while the lead is in
plan mode
works in read-only plan mode until its plan is ready. Switch the lead into plan mode first, then ask for the teammate:
Spawn an architect teammate to refactor the authentication module.
When that teammate finishes planning, it sends a plan approval request to the lead. If you haven’t changed that teammate’s permission mode since it was spawned, Claude Code approves the plan as soon as the request arrives, without the lead reviewing it. The teammate’s edits and commands still go through the permission prompts described in
Permissions
. Once approved, the teammate exits plan mode and begins implementation.
If you put a running in-process teammate in plan mode by pressing
Shift+Tab
while viewing its session, the lead reviews that run’s plan instead of Claude Code approving it. You aren’t asked to approve it; the lead approves it or sends it back for revision.
​
Talk to teammates directly
Each teammate is a full, independent Claude Code session. You can message any teammate directly to give additional instructions, ask follow-up questions, or redirect their approach.
In-process mode
: use the up and down arrow keys in the agent panel to select a teammate, then press Enter to view its session and type to send it a message. Press
x
on a selected teammate to stop it. Press Ctrl+T to toggle the task list.
Split-pane mode
: click into a teammate’s pane to interact with their session directly. Each teammate has a full view of their own terminal.
While you’re viewing an in-process teammate, plain text and
skills
go to that teammate, and built-in commands go to the lead’s session, with these safeguards:
/compact
,
/clear
, and
/rewind
act on the lead’s conversation, so Claude Code asks you to confirm before running one of them from this view.
/model
and
/fast
set the lead’s model and fast mode, not the teammate’s, so they don’t run from this view. A notice tells you why.
A teammate’s model and fast mode are fixed when it spawns.
​
Assign and claim tasks
The shared task list coordinates work across the team. The lead creates tasks and teammates work through them. Tasks have three states: pending, in progress, and completed. A task can also depend on other tasks and shows as blocked in the task list until they’re completed. Teammates don’t self-claim a blocked task, but you or the lead can still assign it.
Agents
without the Task tools
coordinate through messages instead of the shared task list.
The lead can assign tasks explicitly, or teammates can self-claim:
Lead assigns
: tell the lead which task to give to which teammate
Self-claim
: after finishing a task, a teammate picks up the next unassigned, unblocked task on its own
Task claiming uses file locking to prevent race conditions when multiple teammates try to claim the same task simultaneously.
​
Shut down teammates
To gracefully end a teammate’s session, refer to it by name. For example, with a teammate named researcher:
Ask the researcher teammate to shut down
The lead sends a shutdown request. The teammate can approve, exiting gracefully, or reject with an explanation.
The team’s shared directories are cleaned up automatically when the session ends, so there’s no separate cleanup step. See
Architecture
for which directories are removed and which stay on disk.
​
Enforce quality gates with hooks
Use
hooks
to enforce rules when teammates finish work or tasks are created or completed:
TeammateIdle
: runs when a teammate is about to go idle. Exit with code 2 to send feedback and keep the teammate working.
TaskCreated
: runs when a task is being created. Exit with code 2 to prevent creation and send feedback.
TaskCompleted
: runs when a task is being marked complete. Exit with code 2 to prevent completion and send feedback.
​
How agent teams work
This section covers the architecture and mechanics behind agent teams. If you want to start using them, see
Control your agent team
above.
​
How Claude starts agent teams
To start a team, ask Claude for teammates. Claude launches a teammate when it calls the
Agent tool
with a
name
while agent teams are enabled, unless the call is a
fork
or passes
isolation
on the call itself. Claude Code doesn’t ask you to confirm the launch.
Claude also names ordinary subagents on its own so it can message them later. Those calls follow the same rule, so teams can form even when you didn’t ask for one. If you want subagents instead,
turn agent teams off
.
​
Architecture
An agent team consists of:
Component
Role
Team lead
The main Claude Code session that spawns teammates and coordinates work
Teammates
Separate Claude Code instances that each work on assigned tasks
Task list
Shared list of work items that teammates claim and complete
Mailbox
Messaging system for communication between agents
Each agent’s mailbox is a JSON file at
~/.claude/teams/{team-name}/inboxes/{agent-name}.json
. Claude Code validates every entry when it reads a mailbox file. Entries that don’t match the message format are reported as errors and removed from the file; the valid messages are still delivered.
Claude Code reports a message as sent only when the write to the recipient’s mailbox file succeeds, whether the message is plain text or a structured protocol message such as a plan approval or shutdown request. When the write fails, for example because the disk is full or the mailbox directory isn’t writable, the sending agent receives an error and nothing is sent. See
Failed to write to a teammate’s inbox
for the error messages and recovery steps.
Claude Code manages task dependencies automatically: when a teammate completes a task that other tasks depend on, it unblocks the dependent tasks without any action from you.
Teams and tasks are stored locally under a session-derived name. The name is
session-
followed by the first eight characters of the session ID:
Team config
:
~/.claude/teams/{team-name}/config.json
. Claude Code removes the team config directory when the session ends.
Task list
:
~/.claude/tasks/{team-name}/
. This directory stays on disk after the session ends. To change
how long Claude Code keeps it
, set
cleanupPeriodDays
.
Claude Code generates both of these automatically at session startup and updates them as teammates join, go idle, or leave.
The team config holds runtime state such as session IDs and tmux pane IDs, so don’t edit it by hand or pre-author it: your changes are overwritten on the next state update.
To define reusable teammate roles, use
subagent definitions
instead.
The team config contains a
members
array with each member’s name and agent ID. The lead’s entry always carries the agent type
team-lead
. A teammate’s entry carries whatever agent type the lead named when spawning it, whether a
built-in type
or a
subagent definition
, and omits the field when the lead named none. Teammates can read this file to discover other team members.
There is no project-level equivalent of the team config. A file like
.claude/teams/teams.json
in your project directory is not recognized as configuration; Claude treats it as an ordinary file.
​
Use subagent definitions for teammates
When spawning a teammate in either display mode, you can reference a
subagent
type from the project, user, managed, or plugin
subagent scope
. This lets you define a role once, such as a security-reviewer or test-runner, and reuse it both as a delegated subagent and as an agent team teammate.
To use a subagent definition, name it when you ask Claude to spawn the teammate:
Spawn a teammate using the security-reviewer agent type to audit the auth module.
Claude Code reads the subagent definition you named and applies these parts of it to the teammate. Where a part depends on the teammate’s
display mode
, the entry says so:
tools
: Claude Code limits the teammate to the tools in the definition’s
tools
list. For an in-process teammate, Claude Code adds
SendMessage
to that list, and in a
session that has the Task tools
it adds
TaskCreate
,
TaskGet
,
TaskList
, and
TaskUpdate
too.
model
: Claude Code uses the definition’s
model
in either display mode when your spawn prompt doesn’t name one. See
how Claude Code picks a teammate’s model
.
disallowedTools
: for an in-process teammate, Claude Code removes the tools in the definition’s
disallowedTools
from the teammate’s set.
SendMessage
and the Task tools it adds stay available even when the list names them.
effort
: for an in-process teammate, Claude Code applies the definition’s
effort
under the
frontmatter effort rules
.
autoCompactWindow
: for an in-process teammate, Claude Code applies the definition’s
autoCompactWindow
under
that field’s rules
. A split-pane teammate ignores the field. Requires Claude Code v2.1.296 or later.
Body
: for an in-process teammate, Claude Code appends the definition’s body to its default system prompt as additional instructions. For a split-pane teammate, Claude Code uses the body in place of its default system prompt.
skills
: Claude Code doesn’t apply the definition’s
skills
to a teammate in either display mode. The teammate loads skills from your project and user settings.
mcpServers
: for a split-pane teammate, Claude Code applies the definition’s
mcpServers
under the
rules for that field
, which cover a session started with
--agent
as well. An in-process teammate ignores the field and loads MCP servers from your project and user settings.
When Claude messages an in-process teammate that is no longer running, Claude Code brings it back in the same session, restores any conversation saved for it, and gives it the message as its next prompt. After you resume a session, teammates aren’t brought back this way, per
the resume limitation
.
For a teammate it brings back, Claude Code re-applies a definition that came from a project’s
.claude/agents/
directory or an
--add-dir
directory only if you’ve
trusted the folder the agent file is in
. Trusting a parent folder doesn’t count. Until then, the teammate comes back with none of the definition’s tools or instructions, keeping only the tools Claude Code adds to every in-process teammate. See
the teammate’s agent definition was not restored
for the notice text.
​
Permissions
Teammates start with the lead’s permission mode, except
dontAsk
mode
, which they don’t inherit. If the lead runs with
--dangerously-skip-permissions
, all teammates do too. After spawning, you can change an individual teammate’s permission mode, but you can’t set per-teammate permission modes at spawn time.
An
in-process
teammate runs under the lead’s live allow and deny rules, so
--disallowedTools
,
--tools
, and
--allowedTools
all apply to it. For a split-pane teammate, check each flag:
--disallowedTools
and
--tools
: the teammate starts with the lead’s command-line deny rules and tool list. Requires Claude Code v2.1.309 or later.
--allowedTools
: Claude Code doesn’t pass this flag to a split-pane teammate, so an action you allowed with it alone isn’t pre-approved there. To approve those actions ahead of time, put the rules under
permissions.allow
in
--settings
when you start the lead. For example, run
claude --settings '{"permissions":{"allow":["Bash(npm *)"]}}'
in your shell. The rules apply to the lead and each split-pane teammate for that session.
Teammate permission prompts appear in the lead session, so approve them there yourself. You don’t need to approve
a teammate’s plan
.
​
Messages between agents
When one agent sends another a message over
SendMessage
, Claude Code tells the receiving agent the message came from another Claude session, not from you. A teammate can’t approve a permission prompt or supply consent on your behalf, and a teammate that was denied an action can’t relay it to another teammate to bypass the check. The same rules apply to a message that arrives from
one of your other Claude Code sessions
, outside the team entirely.
In
auto mode
, the classifier applies two checks to messages between agents:
It treats an approval claim relayed from another agent as untrusted input rather than confirmation from you.
It reviews each message before Claude Code delivers it, whether a plain message or a structured protocol message such as a shutdown request or plan approval response. A message it blocks never reaches the recipient.
​
Context and communication
Each teammate has its own context window. When spawned, a teammate loads the same project context as a regular session: CLAUDE.md, MCP servers, and skills. If you start the lead with
--setting-sources
, teammates load from the same restricted list of sources. Before v2.1.281,
split-pane
teammates loaded every settings source.
A teammate also receives the spawn prompt from the lead. The lead’s conversation history does not carry over.
How teammates share information:
Automatic message delivery
: when teammates send messages, they’re delivered automatically to recipients. The lead doesn’t need to poll for updates.
Idle notifications
: when a teammate finishes and stops, it automatically notifies the lead and includes its final answer in the notification. A teammate whose turn ends on an API error notifies the lead that it failed and includes the error text.
Shared task list
:
agents that have the Task tools
can see task status and claim available work.
Teammate messaging
: send a message to one specific teammate by name. To reach everyone, send one message per recipient.
The lead assigns every teammate a name when it spawns them, and any teammate can message any other by that name. To get predictable names you can reference in later prompts, tell the lead what to call each teammate in your spawn instruction.
​
Token usage
Agent teams use significantly more tokens than a single session. Each teammate has its own context window, and token usage scales with the number of active teammates. For research, review, and new feature work, the extra tokens are usually worthwhile. For routine tasks, a single session is more cost-effective. See
agent team token costs
for usage guidance.
An in-process teammate’s requests fall outside the main conversation’s
cache TTL bucket
, so its cache holds for five minutes by default, including on a Claude subscription. To keep it for an hour, set
subagentPromptCacheTtl
to
1h
. The API bills 1-hour cache writes at a higher rate.
​
Use case examples
These examples show how agent teams handle tasks where parallel exploration adds value.
​
Run a parallel code review
A single reviewer tends to gravitate toward one type of issue at a time. Splitting review criteria into independent domains means security, performance, and test coverage all get thorough attention simultaneously. The prompt assigns each teammate a distinct lens so they don’t overlap:
Spawn three teammates to review PR #142:
- One focused on security implications
- One checking performance impact
- One validating test coverage
Have them each review and report findings.
Each reviewer works from the same PR but applies a different filter. The lead synthesizes findings across all three after they finish.
​
Investigate with competing hypotheses
When the root cause is unclear, a single agent tends to find one plausible explanation and stop looking. The prompt fights this by making teammates explicitly adversarial: each one’s job is not only to investigate its own theory but to challenge the others’.
Users report the app exits after one message instead of staying connected.
Spawn 5 agent teammates to investigate different hypotheses. Have them talk to
each other to try to disprove each other's theories, like a scientific
debate. Update the findings doc with whatever consensus emerges.
The debate structure is the key mechanism here. Sequential investigation suffers from anchoring: once one theory is explored, subsequent investigation is biased toward it.
With multiple independent investigators actively trying to disprove each other, the theory that survives is much more likely to be the actual root cause.
​
Best practices
​
Give teammates enough context
Teammates load project context automatically, including CLAUDE.md, MCP servers, and skills, but they don’t inherit the lead’s conversation history. See
Context and communication
for details. Include task-specific details in the spawn prompt:
Spawn a security reviewer teammate with the prompt: "Review the authentication module
at src/auth/ for security vulnerabilities. Focus on token handling, session
management, and input validation. The app uses JWT tokens stored in
httpOnly cookies. Report any issues with severity ratings."
​
Choose an appropriate team size
There’s no hard limit on the number of teammates, but practical constraints apply:
Token costs scale linearly
: each teammate has its own context window and consumes tokens independently. See
agent team token costs
for details.
Coordination overhead increases
: more teammates means more communication, task coordination, and potential for conflicts
Diminishing returns
: beyond a certain point, additional teammates don’t speed up work proportionally
Start with 3-5 teammates for most workflows. This balances parallel work with manageable coordination. If you have 15 independent tasks, 3 teammates is a good starting point.
Scale up only when the work benefits from having teammates work simultaneously. Three focused teammates often outperform five scattered ones.
​
Size tasks appropriately
Too small
: coordination overhead exceeds the benefit
Too large
: teammates work too long without check-ins, increasing risk of wasted effort
Just right
: self-contained units that produce a clear deliverable, such as a function, a test file, or a review
The lead breaks work into tasks and assigns them to teammates automatically. If it isn’t creating enough tasks, ask it to split the work into smaller pieces. Having 5-6 tasks per teammate keeps everyone productive and lets the lead reassign work if someone gets stuck.
​
Wait for teammates to finish
Sometimes the lead starts implementing tasks itself instead of waiting for teammates. If you notice this:
Wait for your teammates to complete their tasks before proceeding
​
Start with research and review
If you’re new to agent teams, start with tasks that have clear boundaries and don’t require writing code: reviewing a PR, researching a library, or investigating a bug. These tasks show the value of parallel exploration without the coordination challenges that come with parallel implementation.
​
Avoid file conflicts
Two teammates editing the same file leads to overwrites. Break the work so each teammate owns a different set of files.
​
Monitor and steer
Check in on teammates’ progress, redirect approaches that aren’t working, and synthesize findings as they come in. Letting a team run unattended for too long increases the risk of wasted effort.
​
Troubleshooting
​
Teammates not appearing
If teammates aren’t appearing after you ask Claude to spawn them:
In in-process mode, teammates appear in the agent panel below the prompt input. Use the up and down arrow keys to select one, then press Enter to view it.
A teammate row that disappeared after sitting idle has been hidden, not stopped. Idle rows hide 30 seconds after the whole panel goes idle and reappear on the teammate’s next turn. When more than three teammates are idle, their surplus rows collapse into a single
N idle agents
row that Enter expands. Send the teammate a message by name to bring a hidden row back.
Check that the task you gave Claude was complex enough to warrant a team. Claude decides whether to spawn teammates based on the task.
If you explicitly requested split panes, ensure tmux is installed and available in your PATH:
which
tmux
For iTerm2, verify the
it2
CLI is installed and the Python API is enabled in iTerm2 preferences.
​
Claude spawns teammates instead of subagents
While agent teams are enabled, a subagent that Claude names in the lead’s session launches as a teammate. Claude
can name subagents on its own
, so this can happen during delegation you never framed as team work.
To make named subagents launch as subagents again, turn agent teams off by setting
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
to
0
:
settings.json
{
"env"
: {
"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"
:
"0"
}
}
You don’t need to start a new session: Claude Code reapplies settings-file
env
values to the running session when you save, and rereads the variable each time Claude spawns a subagent, so the next subagent Claude names launches as a subagent.
Setting the variable to
0
in your user
settings.json
overrides a shell export. Other settings sources can still enable agent teams:
Higher-precedence settings files
: project settings, local settings, and a
--settings
payload apply after user settings, so an
env
entry that sets the variable to
1
in any of them wins. See
Settings precedence
.
Managed settings
:
managed settings
apply after every other source. If your organization enables agent teams there, ask your administrator to change the managed value.
After the change, Claude may still name subagents, and the name keeps working as a
SendMessage
address
. Claude receives each subagent’s result when it completes.
​
Too many permission prompts
Teammate permission requests bubble up to the lead, which can create friction. Pre-approve common operations in your
permission settings
before spawning teammates to reduce interruptions.
​
Agents stopping early
Teammates may stop after encountering errors instead of recovering. Check their output by selecting the teammate in the agent panel and pressing Enter in in-process mode, or by clicking the pane in split mode, then either:
Give them additional instructions directly
Spawn a replacement teammate to continue the work
A message from the lead or another teammate wakes an in-process teammate that is waiting to retry a failed API request, so it retries immediately instead of waiting for the full retry delay.
The lead can stop early too, deciding the team is finished before all tasks are actually complete. If that happens, tell it to keep going.
​
Orphaned tmux sessions
If a tmux session persists after the Claude Code session ends, it may not have been fully cleaned up. List sessions and end the one created by the team:
tmux
ls
tmux
kill-session
-t
<
session-nam
e
>
​
Limitations
Agent teams are experimental. Current limitations to be aware of:
No session resumption with in-process teammates
:
/resume
and
/rewind
do not restore in-process teammates. After resuming a session, the lead may attempt to message teammates that no longer exist. If this happens, tell the lead to spawn new teammates.
Task status can lag
: teammates sometimes fail to mark tasks as completed, which blocks dependent tasks. If a task appears stuck, check whether the work is actually done and update the task status manually or tell the lead to nudge the teammate.
Shutdown can be slow
: teammates finish their current request or tool call before shutting down, which can take time.
One team per session
: a session has exactly one team, scoped to that session. You can’t create additional named teams or share a team across sessions.
No nested teams
: teammates cannot spawn their own teammates. Only the lead can manage the team.
No background subagents from in-process teammates
: an in-process teammate’s own subagents run in the foreground, because a teammate’s background work can’t outlive the lead’s process. Claude Code returns an error when a teammate spawns a subagent whose definition sets
background: true
. A teammate’s
run_in_background: true
request also fails, either with an error or by running silently in the foreground. Subagents launched from the main conversation follow the
background default
.
Lead is fixed
: the main session is the lead for its lifetime. You can’t promote a teammate to lead or transfer leadership.
Permissions set at spawn
: teammates start with the permission mode described under
Permissions
. You can change an individual teammate’s permission mode after spawning, but you can’t set per-teammate permission modes at spawn time.
Split panes require tmux or iTerm2
: the default in-process mode works in any terminal. Split-pane mode isn’t supported in VS Code’s integrated terminal, Windows Terminal, or Ghostty.
​
Next steps
Explore related approaches for parallel work and delegation:
Lightweight delegation
:
subagents
spawn helper agents for research or verification within your session, better for tasks that don’t need inter-agent coordination
Messaging between your own sessions
:
cross-session messaging
lets Claude pass findings between the sessions you run yourself
Manual parallel sessions
:
Git worktrees
let you run multiple Claude Code sessions yourself without automated team coordination
Was this page helpful?
Yes
No
{"docsConfig":{"theme":"mint","$schema":"https://mintlify.com/docs.json","name":"Claude Code Docs","description":"Official documentation for Claude Code, Anthropic's agentic coding tool available in the terminal, IDE, desktop app, and browser. Covers installation, configuration, skills, subagents, hooks, MCP, the Agent SDK, and reference material.","colors":{"primary":"#0E0E0E","light":"#D4A27F","dark":"#0E0E0E"},"logo":{"light":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/light.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=78fd01ff4f4340295a4f66e2ea54903c","dark":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/dark.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=1298a0c3b3a1da603b190d0de0e31712"},"favicon":"https://mintcdn.com/claude-code/T2WlxklWBkR5Y1mJ/favicon.ico?fit=max\u0026auto=format\u0026n=T2WlxklWBkR5Y1mJ\u0026q=85\u0026s=346a85952ae08d5ee90e3c34d4423930","appearance":{"default":"system"},"background":{"color":{"light":"#FDFDF7","dark":"#09090B"}},"navbar":{"links":[{"href":"https://platform.claude.com/","label":"Claude Developer Platform"}],"primary":{"type":"button","label":"Open Claude Code","href":"https://claude.ai/code"}},"footer":{"socials":{"x":"https://x.com/AnthropicAI","linkedin":"https://www.linkedin.com/company/anthropicresearch"},"links":[{"header":"Company","items":[{"label":"Anthropic","href":"https://www.anthropic.com/company"},{"label":"Careers","href":"https://www.anthropic.com/careers"},{"label":"Economic Futures","href":"https://www.anthropic.com/economic-futures"},{"label":"Research","href":"https://www.anthropic.com/research"},{"label":"News","href":"https://www.anthropic.com/news"},{"label":"Trust center","href":"https://trust.anthropic.com/"},{"label":"Transparency","href":"https://www.anthropic.com/transparency"}]},{"header":"Help and security","items":[{"label":"Availability","href":"https://www.anthropic.com/supported-countries"},{"label":"Status","href":"https://status.anthropic.com/"},{"label":"Support center","href":"https://support.claude.com/"}]},{"header":"Learn","items":[{"label":"Courses","href":"https://academy.claude.com/"},{"label":"MCP connectors","href":"https://claude.com/partners/mcp"},{"label":"Customer stories","href":"https://www.claude.com/customers"},{"label":"Engineering blog","href":"https://www.anthropic.com/engineering"},{"label":"Events","href":"https://www.anthropic.com/events"},{"label":"Powered by Claude","href":"https://claude.com/partners/powered-by-claude"},{"label":"Service partners","href":"https://claude.com/partners/services"},{"label":"Startups program","href":"https://claude.com/programs/startups"}]},{"header":"Terms and policies","items":[{"label":"Privacy choices","href":"https://www.anthropic.com/legal/privacy"},{"label":"Privacy policy","href":"https://www.anthropic.com/legal/privacy"},{"label":"Disclosure policy","href":"https://www.anthropic.com/responsible-disclosure-policy"},{"label":"Usage policy","href":"https://www.anthropic.com/legal/aup"},{"label":"Commercial terms","href":"https://www.anthropic.com/legal/commercial-terms"},{"label":"Consumer terms","href":"https://www.anthropic.com/legal/consumer-terms"}]}]},"seo":{"metatags":{"canonical":"https://code.claude.com/docs"}},"fonts":{"family":"Anthropic Sans"},"contextual":{"options":["copy","view","claude"],"display":"header"},"styling":{"latex":true},"navigation":{"languages":[{"language":"en","href":"en/overview"},{"language":"fr","href":"fr/overview"},{"language":"de","href":"de/overview"},{"language":"it","href":"it/overview"},{"language":"jp","href":"ja/overview"},{"language":"es","href":"es/overview"},{"language":"ko","href":"ko/overview"},{"language":"zh-CN","href":"zh-CN/overview"},{"language":"zh-TW","href":"zh-TW/overview"},{"language":"ru","href":"ru/overview"},{"language":"id","href":"id/overview"},{"language":"pt-BR","href":"pt/overview"}]}},"deployment":{"deploymentMetadataValue":{"subdomain":"claude-code","hasAudioNarration":false,"actualSubdomain":"claude-code","customDomains":["code.claude.com"],"gitSource":{"type":"github","owner":"anthropics","repo":"claude-code-docs","deployBranch":"main","contentDirectory":"","isPrivate":true,"mountPath":"","label":""},"chroma":{"liveDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85","collectionId":"5857522b-efb8-436a-af8d-9016a7b362b7","schemaVersion":"v3","latestBuiltDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85"},"feedback":{"thumbs":true},"entitlements":{"AI_CHAT":{"status":"ENABLED"},"REMOVE_BRANDING":{"status":"ENABLED"},"CONTEXTUAL_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"CODE_SNIPPET_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"WEB_MCP":{"status":"ENABLED"},"NARRATION":{"status":"ENABLED"}},"buildId":"6ae7a807e7a853c3110bf6c9","clientVersion":"0.0.4044","searchFilterCounts":[{"language":"en","tag":"Agent SDK","count":60},{"language":"en","tag":"Plugins","count":56},{"language":"de","tag":"Neuigkeiten","count":50},{"language":"en","tag":"What's New","count":50},{"language":"es","tag":"Novedades","count":50},{"language":"fr","tag":"Nouveautés","count":50},{"language":"it","tag":"Novità","count":50},{"language":"ko","tag":"새로운 기능","count":50},{"language":"pt-BR","tag":"Novidades","count":50},{"language":"ru","tag":"Что нового","count":50},{"language":"zh-TW","tag":"最新消息","count":50},{"language":"de","tag":"Erste Schritte","count":49},{"language":"es","tag":"Primeros pasos","count":49},{"language":"fr","tag":"Premiers pas","count":49},{"language":"id","tag":"Memulai","count":49},{"language":"it","tag":"Per iniziare","count":49},{"language":"jp","tag":"はじめに","count":49},{"language":"ko","tag":"시작하기","count":49},{"language":"pt-BR","tag":"Primeiros passos","count":49},{"language":"ru","tag":"Начало работы","count":49},{"language":"zh-TW","tag":"快速入門","count":49},{"language":"en","tag":"Getting started","count":48},{"language":"zh-CN","tag":"快速入门","count":46},{"language":"en","tag":"Overview","count":41},{"language":"de","tag":"Agent SDK","count":36},{"language":"en","tag":"Setup and access","count":36},{"language":"es","tag":"Agent SDK","count":36},{"language":"id","tag":"Agent SDK","count":36},{"language":"it","tag":"Agent SDK","count":36},{"language":"jp","tag":"Agent SDK","count":36},{"language":"pt-BR","tag":"Agent SDK","count":36},{"language":"ru","tag":"Agent SDK","count":36},{"language":"zh-CN","tag":"Agent SDK","count":36},{"language":"zh-TW","tag":"Agent SDK","count":36},{"language":"de","tag":"Administration","count":34},{"language":"en","tag":"Administration","count":34},{"language":"es","tag":"Administración","count":34},{"language":"fr","tag":"Administration","count":34},{"language":"id","tag":"Administrasi","count":34},{"language":"it","tag":"Amministrazione","count":34},{"language":"jp","tag":"管理","count":34},{"language":"ko","tag":"관리","count":34},{"language":"pt-BR","tag":"Administração","count":34},{"language":"ru","tag":"Администрирование","count":34},{"language":"zh-CN","tag":"管理","count":34},{"language":"zh-TW","tag":"管理","count":34},{"language":"de","tag":"Plugins","count":32},{"language":"es","tag":"Plugins","count":32},{"language":"fr","tag":"SDK Agent","count":32},{"language":"fr","tag":"Plugins","count":32},{"language":"id","tag":"Plugin","count":32},{"language":"it","tag":"Plugin","count":32},{"language":"jp","tag":"プラグイン","count":32},{"language":"ko","tag":"Agent SDK","count":32},{"language":"ko","tag":"플러그인","count":32},{"language":"pt-BR","tag":"Plugins","count":32},{"language":"ru","tag":"Плагины","count":32},{"language":"zh-CN","tag":"插件","count":32},{"language":"zh-TW","tag":"外掛","count":32},{"language":"en","tag":"Reference","count":28},{"language":"es","tag":"Configuración","count":28},{"language":"jp","tag":"設定","count":28},{"language":"zh-TW","tag":"設定","count":28},{"language":"de","tag":"Konfiguration","count":25},{"language":"en","tag":"Configuration","count":25},{"language":"fr","tag":"Configuration","count":25},{"language":"id","tag":"Konfigurasi","count":25},{"language":"id","tag":"Apa yang Baru","count":25},{"language":"id","tag":"Yang Baru","count":25},{"language":"it","tag":"Configurazione","count":25},{"language":"jp","tag":"新機能","count":25},{"language":"jp","tag":"最新情報","count":25},{"language":"ko","tag":"구성","count":25},{"language":"pt-BR","tag":"Configuração","count":25},{"language":"ru","tag":"Конфигурация","count":25},{"language":"zh-CN","tag":"配置","count":25},{"language":"zh-CN","tag":"新功能","count":25},{"language":"zh-CN","tag":"最新动态","count":25},{"language":"en","tag":"Settings","count":24},{"language":"de","tag":"Mit Claude Code entwickeln","count":22},{"language":"es","tag":"Crea con Claude Code","count":22},{"language":"fr","tag":"Développer avec Claude Code","count":22},{"language":"id","tag":"Membangun dengan Claude Code","count":22},{"language":"it","tag":"Crea con Claude Code","count":22},{"language":"jp","tag":"Claude Code で構築","count":22},{"language":"ko","tag":"Claude Code로 만들기","count":22},{"language":"pt-BR","tag":"Desenvolva com Claude Code","count":22},{"language":"ru","tag":"Разработка с Claude Code","count":22},{"language":"zh-CN","tag":"使用 Claude Code 构建","count":22},{"language":"zh-TW","tag":"使用 Claude Code 打造","count":22},{"language":"de","tag":"Referenz","count":20},{"language":"es","tag":"Referencia","count":20},{"language":"fr","tag":"Référence","count":20},{"language":"id","tag":"Referensi","count":20},{"language":"it","tag":"Riferimento","count":20},{"language":"jp","tag":"リファレンス","count":20},{"language":"ko","tag":"레퍼런스","count":20},{"language":"pt-BR","tag":"Referência","count":20},{"language":"ru","tag":"Справочник","count":20},{"language":"zh-CN","tag":"参考","count":20},{"language":"de","tag":"Plattformen und Integrationen","count":19},{"language":"es","tag":"Plataformas e integraciones","count":19},{"language":"fr","tag":"Plateformes et intégrations","count":19},{"language":"id","tag":"Platform dan integrasi","count":19},{"language":"it","tag":"Piattaforme e integrazioni","count":19},{"language":"jp","tag":"プラットフォームと連携","count":19},{"language":"ko","tag":"플랫폼 및 통합","count":19},{"language":"pt-BR","tag":"Plataformas e integrações","count":19},{"language":"ru","tag":"Платформы и интеграции","count":19},{"language":"zh-CN","tag":"平台与集成","count":19},{"language":"zh-TW","tag":"平台與整合","count":19},{"language":"de","tag":"Code-Review und Pull Requests","count":14},{"language":"es","tag":"Revisión de código y pull requests","count":14},{"language":"fr","tag":"Revue de code et pull requests","count":14},{"language":"it","tag":"Code review e pull request","count":14},{"language":"ko","tag":"코드 리뷰 및 풀 리퀘스트","count":14},{"language":"pt-BR","tag":"Revisão de código e pull requests","count":14},{"language":"ru","tag":"Код-ревью и pull request","count":14},{"language":"zh-TW","tag":"程式碼審查與 pull request","count":14},{"language":"zh-TW","tag":"部署","count":11}]},"assistantConfig":{"enableAskAiButton":false,"enableStarterQuestions":false,"enableAskAiSearchBar":true},"basePath":"/docs","hasChatPermissions":true,"hasWebMcpPermissions":true,"toggles":[{"name":"kill-isr","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"assistant-bash","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"chat-bucketing-batched","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"agent-mintlify-slack","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"agent-integrations-settings","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automations-pr-grouping","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"custom-prefix","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"analytics-v7","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"user-flows-analytics","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"no-publish-flow","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-onboarding","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"llms-txt-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"snapshot-serving-live","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"stripTemperatureMiddleware","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"support-platform-pylon-zendesk","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"snapshot-serving","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"instant-rollback","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"granular-notifications-server","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"granular-notifications","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automations-fable","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"fixed-ai-action-pricing","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automation-resolve-merge-conflict","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"scoped-publishing","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"mintql","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"page-level-analytics","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"editor-version-history-v2","enabled":true,"variant":{"name":"disabled","enabled"

## Source (commands): https://docs.claude.com/en/docs/claude-code/commands

Commands - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
Commands control Claude Code from inside a session. They provide a quick way to switch models, manage permissions, clear context, run a workflow, and more.
Type
/
to see the commands available to you, or type
/
followed by letters to filter.
How the command menu matches what you type
covers highlighting, typos, and the few commands Claude Code hides from the menu until you type their full name.
A command is only recognized at the start of your message. Text that follows the command name becomes its arguments. At the terminal prompt, you can start one message with several
skills
: typing
/skill-a /skill-b do XYZ
loads both skills and passes the trailing text to each as arguments. Up to six skills can be chained.
If you send a command while Claude is responding, Claude Code queues it and runs it after the current turn finishes. Claude Code runs some commands immediately without interrupting the response, such as
/status
,
/tasks
, and
/usage
. In
fullscreen rendering
, Claude Code also opens dialog commands such as
/theme
and
/help
immediately. Before v2.1.234, Claude Code queued those dialogs until the turn finished.
​
Commands across a typical workflow
Most commands are useful at a specific point in a session, from setting up a project to shipping a change.
First session in a repo.
Run
/init
to generate a starter
CLAUDE.md
, then
/memory
to refine it. Use
/mcp
to set up any servers the project needs, ask Claude to create any
subagents
you want, and run
/permissions
to set your approval rules.
During a task.
/plan
switches into plan mode before a large change.
/model
and
/effort
adjust which model you’re using and how much reasoning it applies. When the conversation gets long,
/context
shows what’s filling the window and
/compact
summarizes it to free space. Use
/btw
for a side question that shouldn’t add to the conversation history.
Run work in parallel.
Claude delegates side tasks to
subagents
, and
/tasks
lists the current session’s background work, including subagents that have finished.
/background
detaches the whole session to keep running as a
background agent
and frees your terminal. For a large change that spans the codebase,
/batch
decomposes it into independent units and runs each in its own
worktree
. See
Run agents in parallel
for how these approaches relate.
Before you ship.
/diff
shows what changed.
/code-review
checks the current diff for correctness bugs and can apply the findings with
--fix
; pass a PR number, such as
/code-review high 1234
, to review a pull request instead.
/review
is an alias.
/code-review ultra
runs a multi-agent review in the cloud.
/security-review
checks the diff for security vulnerabilities.
Between sessions.
/clear
starts fresh on a new task while keeping project memory.
/resume
returns to an earlier conversation,
/branch
branches the current one to try a different direction, and
/fork
copies it into a new
background session
.
/teleport
pulls a cloud session into this terminal, and
/remote-control
lets you continue this local session from another device.
When something is wrong.
/rewind
rolls code and conversation back to a checkpoint, or summarizes part of the conversation.
/doctor
runs a setup checkup that diagnoses installation and configuration issues and can fix them,
/debug
diagnoses runtime issues, and
/feedback
reports a bug with session context attached.
​
All commands
The table below lists all the commands included in Claude Code. Most are built-in commands whose behavior is coded into the CLI. Two kinds of entries are marked:
Skill
: a bundled skill. It works like skills you write yourself: a prompt handed to Claude.
/verify
runs only when you invoke it. Before v2.1.215, Claude could also run
/verify
on its own.
Workflow
: a bundled
dynamic workflow
that fans work out across many subagents and runs in the background.
/deep-research
runs only when you invoke it.
To add your own commands, see
skills
.
In the table below,
<arg>
indicates a required argument and
[arg]
indicates an optional one.
Not every command appears for every user. Availability depends on your platform, plan, and environment. For example,
/desktop
only shows on macOS and x64 Windows when signed in with a Claude subscription, and
/upgrade
doesn’t show on Enterprise plans.
Command
Purpose
/add-dir <path>
Add a working directory for file access during the current session. Type a partial path to see matching directory suggestions; press
Tab
to accept one. Most
.claude/
configuration
isn’t discovered
from the added directory. You can’t add most
network paths
, such as
\\server\share
. After a successful add, your
DirectoryAdded
hooks
run. When you run it while Claude is responding, Claude Code asks you to confirm the directory right away, and once you confirm, Claude’s next tool call in the same turn can access it. Before v2.1.234, Claude Code queued the command until the turn finished
/advisor [model|off]
Enable or disable the
advisor tool
, which consults a second model for guidance at key moments during a task. Accepts
fable
,
opus
,
sonnet
, or a full model ID.
fable
requires
Fable access
. Without an argument, opens a picker. In a session without an interactive terminal, or over
Remote Control
, pass the model or
off
as an argument; with no argument there, the command prints the current advisor as text. These forms require Claude Code v2.1.260 or later
/agents
Print a reminder to ask Claude to create or manage
subagents
, or to edit
.claude/agents/
or
~/.claude/agents/
directly. On v2.1.197 and earlier, opens an interactive interface for creating and managing subagent configurations
/artifact-capabilities
Skill
.
Load the reference for the runtime capabilities a published
artifact
can use, such as
calling your connectors
or
offering a file download
, including which ones your account has. Claude normally loads it on its own before building a page that uses one. Available where
artifacts
are
/artifact-diagramming
Skill
.
Load diagramming guidance for Claude to follow in
artifacts
: when a diagram helps, what to draw, and how to write inline SVG that stays legible in light and dark themes. Requires Claude Code v2.1.221 or later
/artifacts
List the
artifacts
you own or that are shared with you, then attach one to the session, open it in your browser, or copy its link. Available where
artifacts
are
/auto-mode-setup
Draft
autoMode.environment
entries
from your project and recent sessions, then review the draft and save it to your user settings. On a Pro, Max, Ultra, or Team plan, requires Claude Code v2.1.228 or later, or v2.1.233 or later on native Windows. On an Enterprise plan or with a Claude Console API key, requires v2.1.283 or later. If the command is missing, see
/auto-mode-setup
returns “Unknown command”
/autocompact [auto|<tokens>]
Set the auto-compact window: how full the context window gets before Claude Code compacts automatically. Pass a size such as
500k
, or
auto
to return to the window tuned for your model. Claude Code saves the value to user settings and applies it to the current session. See
Set the auto-compact window
for accepted values and what overrides it. Without an argument, opens a dialog that shows the current window. Requires Claude Code v2.1.221 or later
/autofix-pr [prompt]
Spawn a
cloud session
that watches the current branch’s PR and pushes fixes when CI fails or reviewers leave comments. Detects the open PR from your checked-out branch with
gh pr view
; to watch a different PR, check out its branch first. By default the cloud session is told to fix every CI failure and review comment; pass a prompt to give it different instructions, for example
/autofix-pr only fix lint and type errors
. Requires the
gh
CLI and access to
cloud sessions
/background [prompt]
Detach the current session to run as a
background agent
and free this terminal. Pass a prompt to send one more instruction before detaching. Monitor the session with
claude agents
. To copy the conversation into a new background session while this one keeps running, use
/fork
. Alias:
/bg
/batch <instruction>
Skill
.
Orchestrate large-scale changes across a codebase in parallel. Researches the codebase, decomposes the work into 5 to 30 independent units, and presents a plan. Once approved, spawns one
background subagent
per unit in an isolated
worktree
. Each subagent implements its unit, runs tests, and publishes its change. Requires a git repository or a
WorktreeCreate
hook
that creates the worktrees. Outside a git repository,
/batch
requires Claude Code v2.1.281 or later. Example:
/batch migrate src/ from JavaScript to TypeScript
/branch [name]
Create a branch of the current conversation at this point, so you can try a different direction without losing the conversation as it stands. Switches you into the branch and preserves the original, which you can return to with
/resume
. To run a copy as a separate
background session
instead of switching into it, use
/fork
; to hand a side task to a
subagent
that reports back into this conversation, use
/subtask
/btw [question]
Ask a
side question
about the current session without adding to the conversation. If you run
/btw
without a question, Claude Code shows your most recent side question so you can browse earlier answers; if you haven’t asked one yet, Claude Code prints a usage line
/bug [report]
Report a bug or share your conversation. You choose how much session history to include and confirm on a consent screen before anything is sent. When you’re signed in to Anthropic on a first-party connection, the report goes to Anthropic; on a third-party provider, or without Anthropic credentials, Claude Code writes the report to a
local archive under
~/.claude/feedback-bundles/
that you forward yourself. In the
VS Code extension
,
/bug
opens the extension’s own feedback dialog instead; requires Claude Code v2.1.229 or later. When you run it while Claude is responding, Claude Code opens the dialog immediately. Before v2.1.232, Claude Code queued the command until the turn finished. Alias:
/share
. Before v2.1.212,
/bug
and
/share
were aliases of
/feedback
/cd <path>
Move this session to a new working directory, keeping the conversation. Type a partial path to see matching directory suggestions; press
Tab
to accept one. For what Claude Code applies from the new directory as soon as you move, and how
/cd
differs from
/add-dir
, see
Move the session to another directory
/chrome
Configure
Claude in Chrome
settings
/claude-api [migrate|upgrade|api-version|managed-agents-onboard|managed-agents-secure|prompt-audit|cost-optimize|build-eval|hillclimb|preserved-thinking-migration]
Skill
.
Load
Claude API
and
Managed Agents
reference material for your project’s language. Also activates automatically when your code imports
anthropic
or
@anthropic-ai/sdk
. For what each subcommand does and the version it requires, see
Work on Claude API projects
/claude-in-chrome [task]
Skill
.
Have Claude carry out a task in your browser, such as testing a page, filling a form, or reading console logs, through
Claude in Chrome
. Available when Chrome integration is enabled for the session, for example with
claude --chrome
, or when Claude Code can offer to
install the extension
/clear [name]
Start a new conversation with empty context. Pass a name to label the previous conversation in the
/resume
picker. To free up context while continuing the same conversation, use
/compact
instead. Resume the previous conversation with
/resume
, or, in the same Claude Code process, restore it from
the rewind menu’s previous-session entry
. Aliases:
/reset
,
/new
/code-review [low|medium|high|xhigh|max|ultra] [--fix] [--comment] [--max-findings n|all|default] [pr#|branch|path]
Skill
.
Review the current diff, or a PR number, branch, or path you pass, for correctness bugs. Depending on your model and effort level, the review also covers cleanup opportunities. Pass
--fix
to have Claude apply the findings,
--comment
to post them on the GitHub PR or GitLab merge request, or
ultra
to run a deep
cloud review
. Posting to a GitLab merge request requires Claude Code v2.1.257 or later. With
ultra
on a
github.com
PR target, pass
--post
to preselect
posting the finished findings to the PR
in the launch dialog;
--post
requires Claude Code v2.1.227 or later. See
Review locally with
/code-review
for the effort levels, targeting, and how it relates to
/simplify
. Alias:
/review
/color [color|default]
Set the prompt bar color for the current session. Available colors:
red
,
blue
,
green
,
yellow
,
purple
,
orange
,
pink
,
cyan
. Use
default
to reset, or run with no argument to pick a random color. When
Remote Control
is connected, the color syncs to claude.ai/code. Also available in non-interactive mode (
-p
)
/compact [instructions]
Free up context by summarizing the conversation so far. Optionally pass focus instructions for the summary. See
how compaction handles rules, skills, and memory files
/config [key=value ...]
Open the
Settings
interface to adjust theme, model,
output style
, and other preferences. Pass one or more
key=value
pairs to set a setting directly without opening the interface, for example
/config thinking=false
,
/config theme=dark
, or
/config model=sonnet
. The
key=value
form also works in non-interactive mode (
-p
) and from the Claude mobile app via
Remote Control
. The
key=value
form can’t turn on a setting that needs your confirmation in the panel, such as
autoContinueAtUsageLimit
, though it can turn one off. Run
/config --help
to list the keys it accepts. Alias:
/settings
/context [all]
Visualize current context usage as a colored grid. Shows optimization suggestions for context-heavy tools, memory bloat, and capacity warnings. When the conversation exceeds the context window, the output includes a
warning
showing how far over the limit you are and which command frees space. In
fullscreen mode
,
/context
collapses the per-item breakdown to keep the grid visible. Pass
all
to expand it
/copy [N]
Copy the last assistant response to clipboard. Pass a number
N
to copy the Nth-latest response:
/copy 2
copies the second-to-last. When code blocks or blockquotes are present, shows an interactive picker to select individual blocks or the full response. Press
w
in the picker to write the selection to a file instead of the clipboard, which is useful over SSH
/cost
Alias for
/usage
/dataviz [request]
Skill
.
Design guidance for charts, graphs, and dashboards. Claude picks the chart form for the data, assigns color by role, validates the palette for colorblind safety and contrast with a bundled script, and applies mark, interaction, and accessibility rules. Uses a brand-neutral placeholder palette that you replace with your own
/debug [description]
Skill
.
Enable debug logging for the current session and troubleshoot issues by reading the session debug log. Debug logging is off by default unless you started with
claude --debug
, so running
/debug
mid-session starts capturing logs from that point forward. Optionally describe the issue to focus the analysis
/deep-research <question>
Workflow
.
Fan out web searches on a question, fetch and cross-check sources, and synthesize a cited report
/design [brief]
Skill
.
Draft UI mockups, screen flows, landing pages, or posters as artboards on one canvas, published as a Claude Design
artifact
, for example
/design a settings screen for a mobile banking app
. You edit the artboards in a desktop browser, and your edits save automatically. You can export each artboard as PNG or PDF. Requires Claude Code v2.1.265 or later, a session where
artifacts are available
, and an account where the
Design template is available
; if your organization has turned that template off,
/design
doesn’t draft designs. Available on the Anthropic API. On Amazon Bedrock, Google Cloud’s Agent Platform, Microsoft Foundry, and Claude Platform on AWS, artifacts aren’t available, so the command is unavailable there
/design consent
,
/design revoke
Grant Claude access to
Claude Design
, or withdraw it. When a reply from Claude asks you to run
/design consent
, type it at the Claude Code prompt yourself
/design-login
Authorize design-system access for
/design-sync
with your claude.ai account. Sign in with
/design-login
whenever
/design-sync
or
/design consent
tells you to. This sign-in is for the standalone Claude Design site at claude.ai/design, which closes by December 14, 2026; see
Migrate from standalone Claude Design to Claude
/design-sync [hint]
Skill
.
Convert your repo’s React design system and upload it to
Claude Design
, so designs it produces use your real components. Optionally name the design system, for example
/design-sync Acme DS
. A first-time sync verifies every component and can take a few hours on a large repo. Available on the Anthropic API. It needs claude.ai, which the CLI doesn’t contact on Amazon Bedrock, Google Cloud’s Agent Platform, Microsoft Foundry, or Claude Platform on AWS, or through a
Claude apps gateway
. The command is unavailable there. This command uploads to the standalone claude.ai/design site, which closes by December 14, 2026; see
Migrate from standalone Claude Design to Claude
/desktop
Continue the current session in the Claude Code Desktop app. Requires macOS or x64 Windows and a Claude subscription. Alias:
/app
/diff
Review the changes in your working tree, including the edits Claude has made so far. See
Review changes with /diff
/doctor [prompt-audit [path]]
Skill
.
Run a setup checkup that diagnoses installation, settings, extension, and
CLAUDE.md
problems and proposes fixes that Claude applies after you confirm. For what the checkup covers, or to audit your instructions with
prompt-audit
instead, see
Check your setup with
/doctor
. The
prompt-audit
subcommand requires Claude Code v2.1.283 or later. Alias:
/checkup
/effort [level|auto|status|ultracode [on|off]]
Set the
effort level
:
low
to
xhigh
,
max
, or
auto
;
status
prints it.
ultracode
or
ultracode on
turns
ultracode
on for the session, and
ultracode off
turns it off; the
ultracode
key persists.
max
is session-only. The
on
and
off
arguments require Claude Code v2.1.284 or later. If you run
/effort
while Claude is working, see
when the new level starts
. Works in
-p
on v2.1.205 or later
/exit
Exit the CLI. In an attached
background session
, this detaches and the session keeps running. Alias:
/quit
/export [filename]
Export the current conversation as plain text. With a filename, writes directly to that file. Without, opens a dialog to copy to clipboard or save to a file
/fast [on|off]
Toggle
fast mode
on or off. Run it while Claude is responding and Claude Code toggles fast mode without waiting for the turn to end, though the running turn finishes at its original speed. Before v2.1.242, Claude Code decided from a feature flag it fetched from Anthropic whether to run the command mid-turn or queue it until the turn finished, and always queued it in a session that doesn’t
fetch feature flags
. Availability in non-interactive mode with
-p
is limited; see
Toggle fast mode
/feedback [report]
Send product feedback about Claude Code. Opens the same dialog as
/bug
, with the same consent step, sending rules, and mid-turn behavior. In sessions with
Claude-drafted feedback
,
/feedback
with no argument opens the drafts queue instead, where you review, edit, send, or discard the drafts Claude queued; the queue includes an option to write a new report in the dialog. With an argument, and for
/bug
always, the dialog opens directly
/fewer-permission-prompts
Skill
.
Scan your transcripts for common read-only Bash and MCP tool calls, then add a prioritized allowlist to project
.claude/settings.json
to reduce permission prompts
/focus
Toggle the focus view, which shows only your last prompt, a one-line tool-call summary with edit diffstats, and the final response. The tool-call summary also counts the subagents launched in the turn and collapses completed background-task notifications into a single count. The selection persists across sessions; set
viewMode
in settings to override it. Only available in
fullscreen rendering
. From a
Remote Control
client, run
/focus [on|off]
to turn the focus view on or off for the current session only, without changing your saved selection; this requires Claude Code v2.1.281 or later. The
VS Code extension
offers its own Focus view as a command-menu toggle, stored as an extension setting, independent of
viewMode
/fork [prompt]
Copy the current conversation
into a new background session and keep working here. Pass a prompt and the copy starts working on it immediately; without one it waits in agent view for its first prompt. Except when the copy
edits in place
, Claude Code instructs it to create a worktree of its own before making code changes; the isolation instruction requires Claude Code v2.1.221 or later. To hand a side task to a subagent whose result comes back into this conversation, use
/subtask
; to switch into a copy yourself, use
/branch
. When
agent view is turned off
,
/fork
starts a
forked subagent
instead
/goal [condition|clear]
Set a
goal
: Claude keeps working across turns until the condition is met or the goal
clears for another reason
. With no argument, shows the current or most recently achieved goal.
clear
,
stop
,
off
,
reset
,
none
, or
cancel
removes an active goal early
/heapdump
Write a JavaScript heap snapshot and a memory breakdown to
~/Desktop
, or your home directory on Linux without a Desktop folder, for diagnosing high memory usage. Attach only the
-diagnostics.json
file when reporting a memory issue; the
.heapsnapshot
contains your full conversation and credentials, so don’t share it.
Hidden from the command menu
; type it in full. See
what to do with the output
/help
Show help and available commands
/hooks
View
hook
configurations
/ide
Manage IDE integrations and show status
/import [codex|gemini|cursor] [--dry-run] [--yes]
Bring configuration from OpenAI Codex, Google Gemini CLI, or Cursor on your machine into Claude Code, including instruction files, MCP servers, commands, subagents, and skills. In
non-interactive mode
with
-p
,
/import
lists what it found and gives you the command that confirms the import. Add
--dry-run
to preview without writing anything, or
--yes
to skip the interactive picker. Not available on Amazon Bedrock, Google Cloud’s Agent Platform, Microsoft Foundry, or Claude Platform on AWS, or through a
Claude apps gateway
. Also unavailable when you turn off
feature-flag fetching
. Importing from Cursor requires v2.1.265 or later
/init
Initialize project with a
CLAUDE.md
guide. Set
CLAUDE_CODE_NEW_INIT=1
for an interactive flow that also walks through skills, hooks, and personal memory files. If
/init
finds OpenAI Codex or Google Gemini CLI configuration, it offers to carry it over with
/import
/insights
Generate an HTML report analyzing your recent sessions on this machine: which projects you work in, how you use Claude Code, where things go wrong, and features to try. Not available in
cloud sessions
. See
Analyze your usage patterns
for the report location, retention, and cost
/install-github-app
Install the Claude GitHub App for a repository, with an optional step to set up
GitHub Actions
workflows and secrets. Walks you through selecting a repo and configuring the integration. Works only with github.com repositories. When your repository’s git remote is on gitlab.com or bitbucket.org, the command prints a notice and exits instead of starting setup. To run Claude Code from GitLab pipelines, see
GitLab CI/CD
/install-slack-app
Install the Claude Slack app. Opens a browser to complete the OAuth flow
/keybindings
Open your
keyboard shortcuts
file
/list-agents
List the subagents,
agent team
teammates, and other Claude Code sessions Claude can message, with the name to use for each. See
cross-session messaging
. Also available as
/peers
. Requires Claude Code v2.1.224 or later; earlier versions report
Unknown command: /list-agents
. Teammate rows and the first line showing this session’s own name require v2.1.239 or later. Available only in sessions where
cross-session messaging is enabled
/login
Sign in to your Anthropic account
/logout
Sign out from your Anthropic account
/loop [interval] [prompt]
Skill
.
Run a prompt repeatedly while the session stays open. Omit the interval and Claude
self-paces between iterations
. Omit the prompt and Claude runs the
built-in maintenance prompt
or your
loop.md
. Example:
/loop 5m check if the deploy finished
. See
Run prompts on a schedule
. Alias:
/proactive
/mcp [reconnect (<server>|all)|enable|disable [<server>|all]]
Manage MCP server connections and OAuth authentication. Run with no argument to open the interactive list, or pass
reconnect
,
enable
, or
disable
with a server name or
all
to change connection state without opening it.
reconnect all
retries every server that failed or needs authentication
. In non-interactive mode (
-p
), running it with no argument prints a text summary of server status instead of opening the list
/memory
Edit
CLAUDE.md
files, enable or disable
auto memory
, and view auto memory entries
/mobile
Show QR code to download the Claude mobile app. Aliases:
/ios
,
/android
/model [model]
Switch the AI model and save it as your default for new sessions. For models that support it, use left/right arrows to
adjust effort level
. With no argument, opens a picker; press
s
on a row to switch for the current session only. See
when the new model starts
. Before v2.1.242, it could wait. With
-p
, pass a model argument, which isn’t saved as your default; requires v2.1.205 or later
/output-style [style]
List
output styles
or switch to one, for example
/output-style concise
. See
Change your output style
. Requires Claude Code v2.1.269 or later
/passes
Share a free week of Claude Code with friends. Only visible if your account is eligible
/permissions
Manage allow, ask, and deny rules for tool permissions. Opens an interactive dialog where you can view rules by scope, add or remove rules, manage working directories, and review
recent auto mode denials
. You can also view and edit
auto mode classifier rules
from the dialog’s
Auto mode
tab. When you run it while Claude is responding, Claude Code opens the dialog immediately and applies your changes starting with Claude’s next tool call in the same turn. Before v2.1.234, Claude Code queued the command until the turn finished. Alias:
/allowed-tools
/plan [description]
Enter plan mode directly from the prompt. Pass an optional description to enter plan mode and immediately start with that task, for example
/plan fix the auth bug
/plugin [subcommand]
Manage Claude Code
plugins
. Run with no argument to open the plugin menu, or pass a subcommand such as
list
,
install
,
enable
, or
disable
to act directly. Claude Code can activate a plugin during the install; the
install summary
tells you whether it did or whether to run
/reload-plugins
/plugin-authoring
Load the reference Claude works from to
write a mod
. Claude can load it on its own when you ask for a mod. This is a skill from a
built-in plugin
, which you can turn off in
/plugin
. Requires Claude Code v2.1.287 or later
/powerup
Discover Claude Code features through quick interactive lessons with animated demos
/pr-comments [PR]
Removed in v2.1.91. Ask Claude directly to view pull request comments instead. On earlier versions, fetches and displays comments from a GitHub pull request; automatically detects the PR for the current branch, or pass a PR URL or number. Requires the
gh
CLI
/privacy-settings
View and update your privacy settings. Only available for Pro, Max, and Ultra plan subscribers
/radio
Open Claude FM lo-fi radio in your browser. Prints the stream URL when no browser is available
/rate-limit-options
Show ways to keep working when a claude.ai usage limit blocks a request: wait and
continue automatically when the limit resets
, add
usage credits
, or upgrade your plan. Claude Code can also open this menu on its own when you hit a limit at your own terminal. See
Turn automatic continue off
. Requires a claude.ai subscription. The wait-and-continue rows require Claude Code v2.1.234 or later
/recap
Generate a one-line summary of the current session on demand. See
Session recap
for the automatic recap that appears after you’ve been away
/release-notes
View the changelog in an interactive version picker. Select a specific version to see its release notes, or choose to show all versions. The notes appear in your transcript without entering the conversation Claude sees
/reload-plugins [--force]
Reload all active
plugins
to apply pending changes without restarting. Reports counts for each reloaded component and flags any load errors. When the reload would change which MCP tools are loaded and invalidate the prompt cache, the command warns and skips unless you pass
--force
. Also available in non-interactive mode (
-p
), the Agent SDK, and the desktop app, where it runs only on input typed directly into the session and doesn’t apply plugin MCP server changes; requires Claude Code v2.1.260 or later. See
Apply plugin changes without restarting
/reload-skills
Re-scan
skill
and command directories so skills added or changed on disk during the session become available without restarting. Reports how many skills are available and how many were added or removed
/remote-control
Make this session available for
Remote Control
from claude.ai. Running it while signed out prints that Remote Control requires a claude.ai subscription and tells you how to sign in. Alias:
/rc
/remote-env
Choose the default
cloud environment
for cloud sessions you start from the CLI
/rename [name]
Rename the current session and show the name on the prompt bar. Without a name, auto-generates one from conversation history. Also available in non-interactive mode (
-p
). From every rename surface, including claude.ai and the desktop app, Claude Code replaces control and invisible characters in the new name with spaces and caps the name at 200 characters. If the name is empty once invisible characters are removed, Claude Code rejects it and shows
That name is empty once invisible characters are removed. Usage: /rename <name>
. The character replacement and length cap require Claude Code v2.1.221 or later
/restart
Restart Claude Code and resume this session, which applies an installed update. Run it when the footer offers it after an update installs. Requires a Pro, Max, or Ultra plan and a native install on macOS or Linux, not WSL. Requires Claude Code v2.1.288 or later. Alias:
/update
/resume [session]
Resume a conversation by ID or name, or open the session picker.
Background sessions
appear in the picker marked with
bg
. Resuming one that is still running, from the picker or by ID or name,
opens that session
: your current conversation moves to the background and this terminal attaches to the running one. Press
←
on an empty prompt to return to agent view, which also lists the conversation you left. Before v2.1.285, Claude Code refused and told you to open the session with
claude attach
or stop it first. Alias:
/continue
/review [low|medium|high|xhigh|max|ultra] [--fix] [--comment] [--max-findings n|all|default] [pr#|branch|path]
Alias of
/code-review
: reviews the current diff, or a PR number, branch, or path you pass, such as
/review 1234
, and takes the same effort levels and flags. With no level given, the review reuses the last
low
through
max
level you typed; see
Review locally with
/code-review
for the exact rules. For a deep cloud review, use
/code-review ultra
. Before v2.1.223,
/review
was a separate command that ran a single-pass, read-only review of a GitHub pull request by number, listing open PRs to pick from when run with no argument; from v2.1.186 through v2.1.201, it ran the same multi-agent engine as
/code-review medium
/rewind
Rewind the conversation and/or code to a previous point, or summarize from a selected message. See
checkpointing
. Aliases:
/checkpoint
,
/undo
/run
Skill
.
Launch and drive your project’s app to see a change working, not only passing tests. See
Run and verify your app
/run-skill-generator
Skill
.
Teach
/run
and
/verify
how to build, launch, and drive your project’s app from a clean environment by writing a per-project
skill
/sandbox
Toggle
sandbox mode
. Available on supported platforms only
/schedule [description]
Create, update, list, or run
cloud scheduled tasks
, formerly routines. Claude walks you through the setup conversationally. You can also ask about a
scheduled task’s recent runs
. Alias:
/routines
/scroll-speed
Adjust mouse wheel
scroll speed
interactively. Available in
fullscreen rendering
only and not in the JetBrains IDE terminal
/security-review
Analyze the changes on your current branch for security vulnerabilities. Reviews the diff between your branch and origin’s default branch, identifying risks like injection, auth issues, and data exposure. Needs an
origin
remote; if the review fails with an
ambiguous argument
error, see the
error reference
/setup-bedrock
Configure
Amazon Bedrock
authentication, region, and model pins through an interactive wizard.
Hidden from the command menu
until
CLAUDE_CODE_USE_BEDROCK=1
is set; type it in full. First-time Amazon Bedrock users can also access this wizard from the login screen
/setup-vertex
Configure
Google Cloud’s Agent Platform
authentication, project, region, and model pins through an interactive wizard.
Hidden from the command menu
until
CLAUDE_CODE_USE_VERTEX=1
is set; type it in full. First-time Google Cloud’s Agent Platform users can also access this wizard from the login screen
/simplify [target]
Skill
.
Review the changed code for cleanup opportunities and apply the fixes. Four review
agents
run in parallel, covering reuse of existing helpers, simplification, efficiency, and whether the change is at the right level of abstraction. The review doesn’t look for correctness bugs. Use
/code-review
to find bugs. Pass a path or PR reference to review a specific target
/skill-doctor
Show what each of your
skills
costs in context and how often it gets used, so you can
find skills to turn off
. Requires Claude Code v2.1.252 or later and
feature-flag fetching
/skills
List available
skills
. Type to filter the list by name, description, or source. Press
t
to sort by token count,
Space
or
Enter
to
cycle a skill’s visibility to Claude and the
/
menu
, and
Esc
to save and close. You can’t cycle plugin skills, skills whose frontmatter sets
disable-model-invocation: true
, or skills with a
skillOverrides
entry in managed settings or the
--settings
flag
/slides [brief]
Skill
.
Make a new presentation as a Claude Slides
artifact
filled from your brief, for example
/slides a quarterly review of the platform team
. Requires Claude Code v2.1.265 or later, a session where
artifacts are available
, and an account where the
Slides template is available
; otherwise the command doesn’t appear. Available on the Anthropic API. On Amazon Bedrock, Google Cloud’s Agent Platform, Microsoft Foundry, and Claude Platform on AWS, artifacts aren’t available, so the command is unavailable there
/stats
Alias for
/usage
. Opens on the Stats tab
/status
Open the Settings interface on the Status tab, showing version, model, account, and connectivity. A
Session kind
row reads
background job · attached
or
background job · unattended
in a
background session
, depending on whether a terminal is attached, and
interactive
in any other session. Before v2.1.221,
/status
didn’t show this row. Works while Claude is responding
/statusline
Configure Claude Code’s
status line
. Describe what you want, or run without arguments to auto-configure from your shell prompt
/stickers
Order Claude Code stickers
/stop
Stop the
background session
you’re attached to, or the one you send it to as a
peek reply
; the transcript and any worktree are kept. To detach without stopping, use
/exit
or press
←
/subtask <task>
Spawn a
forked subagent
: a background subagent that inherits the full conversation and works on the task while you keep working. Its result returns to this conversation when it finishes. To copy the conversation into a separate background session instead, use
/fork
. When
agent view is turned off
,
/subtask
isn’t available and
/fork
spawns the forked subagent instead
/tasks
View and manage background work in the current session, including subagents that have finished. Also available as
/bashes
/team-onboarding
Generate a team onboarding guide from your Claude Code usage history. Claude analyzes your sessions, commands, and MCP server usage from the past 30 days. It produces a markdown guide a teammate can paste as a first message to get set up quickly. For claude.ai subscribers on Team and Enterprise plans, also returns a share link teammates can open directly in Claude Code
/teleport
Pull a
cloud session
into this terminal. Opens a picker, then fetches the branch and conversation. Also available as
/tp
. Requires a claude.ai subscription
/terminal-setup
Install a Shift+Enter keybinding for newlines
in VS Code, Cursor, Devin Desktop, Alacritty, or Zed. In Apple Terminal,
enable Option+Enter for newlines and turn off the audible bell
instead. In iTerm2,
turn on clipboard access so that
/copy
works
/theme
Change the color theme. Includes an
auto
option that matches your terminal’s light or dark background, light and dark variants, colorblind-accessible (daltonized) themes, ANSI themes that use your terminal’s color palette, and any
custom themes
from
~/.claude/themes/
or plugins. Select
New custom theme…
to create one
/tui [default|fullscreen]
Set the terminal UI renderer and relaunch into it with your conversation intact.
fullscreen
enables the
flicker-free alt-screen renderer
. With no argument, prints the active renderer
/ultraplan <prompt>
Removed. Use
plan mode
instead. Previously sent a planning task to a
cloud session
for review in your browser
/ultrareview [PR or branch]
Run a deep, multi-agent code review in a cloud sandbox with
ultrareview
. Pass a PR reference to review that pull request, or a base branch or commit to change the comparison base. The preferred invocation is
/code-review ultra
, and
/ultrareview
is an alias. Includes 3 free runs on Pro, Max, and Ultra, then requires
usage credits
/update-config [request]
Skill
.
Describe a settings change, such as allowing a command, setting an environment variable, or adding a
hook
, and Claude edits the matching
settings.json
file. For options such as theme and model, use
/config
instead
/upgrade
Open the upgrade page in your browser to switch to a higher plan tier. When the browser fails to open, the command shows a sign-in prompt without printing the URL
/usage
Show session cost, plan usage limits, and activity stats. On a Pro, Max, Ultra, Team, or Enterprise plan, includes a
breakdown of what counts against your plan limits
.
/cost
and
/stats
are aliases
/usage-credits
Configure usage credits, or request them from your admin, when you hit a limit. Opens your
usage-credits billing settings
in the browser, except that Team and Enterprise members without billing access instead send a usage-credits request to their admin from the CLI, after confirming in a dialog that the request notifies their admins. When no browser can open the billing page, for example over SSH, the command prints the URL to visit instead; this requires Claude Code v2.1.205 or later, and earlier versions showed nothing in that case. Previously
/extra-usage
/verify
Skill
.
Confirm a code change does what it should by building your project’s app, running it, and observing the result, rather than relying on tests or type checks. See
Run and verify your app
/vim
Removed in v2.1.92. To toggle between Vim and Normal editing modes, use
/config
→ Editor mode
/voice [hold|tap|off]
Toggle
voice dictation
, or enable it in a specific mode. Requires a Claude.ai account
/web-setup
Connect your GitHub account for
cloud sessions
using your local
gh
CLI credentials
/workflow-authoring
Skill
.
Load the reference for writing
dynamic workflow
scripts: the script API, resume behavior, quality patterns, and worked examples. Claude normally loads it on its own before writing a script; run it yourself before
editing a saved script by hand
. Available when dynamic workflows are enabled, and requires Claude Code v2.1.248 or later
/workflows
Open the
workflow
progress view to watch, pause, resume, or save running and completed workflows
​
How the command menu matches what you type
Claude Code filters the
/
menu as you type. Each bullet below covers one thing you might notice while filtering:
Highlighting
: Claude Code highlights the top suggestion only when the letters after the
/
match a command’s name or alias, from the start of the name or from a word within it, ignoring the
:
,
_
, and
-
separators. Typing
/adddir
highlights
/add-dir
, and typing
/new
highlights
/clear
through its alias. Press
Enter
to run the highlighted suggestion. These highlighting rules require Claude Code v2.1.236 or later.
After a typo
: Claude Code highlights nothing. The close matches stay listed, and you can pick one with
Tab
or the arrow keys, but
Enter
submits your text as typed and reports
Unknown command
.
Commands that aren’t available to you
: Claude Code leaves them out of the menu. When nothing matches, Claude Code shows
No commands match "/name"
. Most unavailable commands return
Unknown command
when you submit them; a few, such as
/schedule
on a Console API key
, answer with their own availability message instead. Some commands also answer with a message of their own when your organization’s policy disables them.
Hidden commands
: Claude Code keeps a few available commands, such as
/heapdump
, out of the menu by design. A partial name never brings a hidden command into the menu: if the partial matches nothing visible, Claude Code shows the same no-match message. Claude Code lists the command only once you’ve typed its full name, and submitting the full name runs it.
​
MCP prompts
MCP servers can expose prompts that appear as commands. See
MCP prompts
for details.
​
See also
Skills
: create your own commands
Interactive mode
: keyboard shortcuts, Vim mode, and command history
CLI reference
: launch-time flags
Was this page helpful?
Yes
No
{"docsConfig":{"theme":"mint","$schema":"https://mintlify.com/docs.json","name":"Claude Code Docs","description":"Official documentation for Claude Code, Anthropic's agentic coding tool available in the terminal, IDE, desktop app, and browser. Covers installation, configuration, skills, subagents, hooks, MCP, the Agent SDK, and reference material.","colors":{"primary":"#0E0E0E","light":"#D4A27F","dark":"#0E0E0E"},"logo":{"light":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/light.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=78fd01ff4f4340295a4f66e2ea54903c","dark":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/dark.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=1298a0c3b3a1da603b190d0de0e31712"},"favicon":"https://mintcdn.com/claude-code/T2WlxklWBkR5Y1mJ/favicon.ico?fit=max\u0026auto=format\u0026n=T2WlxklWBkR5Y1mJ\u0026q=85\u0026s=346a85952ae08d5ee90e3c34d4423930","appearance":{"default":"system"},"background":{"color":{"light":"#FDFDF7","dark":"#09090B"}},"navbar":{"links":[{"href":"https://platform.claude.com/","label":"Claude Developer Platform"}],"primary":{"type":"button","label":"Open Claude Code","href":"https://claude.ai/code"}},"footer":{"socials":{"x":"https://x.com/AnthropicAI","linkedin":"https://www.linkedin.com/company/anthropicresearch"},"links":[{"header":"Company","items":[{"label":"Anthropic","href":"https://www.anthropic.com/company"},{"label":"Careers","href":"https://www.anthropic.com/careers"},{"label":"Economic Futures","href":"https://www.anthropic.com/economic-futures"},{"label":"Research","href":"https://www.anthropic.com/research"},{"label":"News","href":"https://www.anthropic.com/news"},{"label":"Trust center","href":"https://trust.anthropic.com/"},{"label":"Transparency","href":"https://www.anthropic.com/transparency"}]},{"header":"Help and security","items":[{"label":"Availability","href":"https://www.anthropic.com/supported-countries"},{"label":"Status","href":"https://status.anthropic.com/"},{"label":"Support center","href":"https://support.claude.com/"}]},{"header":"Learn","items":[{"label":"Courses","href":"https://academy.claude.com/"},{"label":"MCP connectors","href":"https://claude.com/partners/mcp"},{"label":"Customer stories","href":"https://www.claude.com/customers"},{"label":"Engineering blog","href":"https://www.anthropic.com/engineering"},{"label":"Events","href":"https://www.anthropic.com/events"},{"label":"Powered by Claude","href":"https://claude.com/partners/powered-by-claude"},{"label":"Service partners","href":"https://claude.com/partners/services"},{"label":"Startups program","href":"https://claude.com/programs/startups"}]},{"header":"Terms and policies","items":[{"label":"Privacy choices","href":"https://www.anthropic.com/legal/privacy"},{"label":"Privacy policy","href":"https://www.anthropic.com/legal/privacy"},{"label":"Disclosure policy","href":"https://www.anthropic.com/responsible-disclosure-policy"},{"label":"Usage policy","href":"https://www.anthropic.com/legal/aup"},{"label":"Commercial terms","href":"https://www.anthropic.com/legal/commercial-terms"},{"label":"Consumer terms","href":"https://www.anthropic.com/legal/consumer-terms"}]}]},"seo":{"metatags":{"canonical":"https://code.claude.com/docs"}},"fonts":{"family":"Anthropic Sans"},"contextual":{"options":["copy","view","claude"],"display":"header"},"styling":{"latex":true},"navigation":{"languages":[{"language":"en","href":"en/overview"},{"language":"fr","href":"fr/overview"},{"language":"de","href":"de/overview"},{"language":"it","href":"it/overview"},{"language":"jp","href":"ja/overview"},{"language":"es","href":"es/overview"},{"language":"ko","href":"ko/overview"},{"language":"zh-CN","href":"zh-CN/overview"},{"language":"zh-TW","href":"zh-TW/overview"},{"language":"ru","href":"ru/overview"},{"language":"id","href":"id/overview"},{"language":"pt-BR","href":"pt/overview"}]}},"deployment":{"deploymentMetadataValue":{"subdomain":"claude-code","hasAudioNarration":false,"actualSubdomain":"claude-code","customDomains":["code.claude.com"],"gitSource":{"type":"github","owner":"anthropics","repo":"claude-code-docs","deployBranch":"main","contentDirectory":"","isPrivate":true,"mountPath":"","label":""},"chroma":{"liveDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85","collectionId":"5857522b-efb8-436a-af8d-9016a7b362b7","schemaVersion":"v3","latestBuiltDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85"},"feedback":{"thumbs":true},"entitlements":{"AI_CHAT":{"status":"ENABLED"},"REMOVE_BRANDING":{"status":"ENABLED"},"CONTEXTUAL_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"CODE_SNIPPET_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"WEB_MCP":{"status":"ENABLED"},"NARRATION":{"status":"ENABLED"}},"buildId":"6ae7a807e7a853c3110bf6c9","clientVersion":"0.0.4044","searchFilterCounts":[{"language":"en","tag":"Agent SDK","count":60},{"language":"en","tag":"Plugins","count":56},{"language":"de","tag":"Neuigkeiten","count":50},{"language":"en","tag":"What's New","count":50},{"language":"es","tag":"Novedades","count":50},{"language":"fr","tag":"Nouveautés","count":50},{"language":"it","tag":"Novità","count":50},{"language":"ko","tag":"새로운 기능","count":50},{"language":"pt-BR","tag":"Novidades","count":50},{"language":"ru","tag":"Что нового","count":50},{"language":"zh-TW","tag":"最新消息","count":50},{"language":"de","tag":"Erste Schritte","count":49},{"language":"es","tag":"Primeros pasos","count":49},{"language":"fr","tag":"Premiers pas","count":49},{"language":"id","tag":"Memulai","count":49},{"language":"it","tag":"Per iniziare","count":49},{"language":"jp","tag":"はじめに","count":49},{"language":"ko","tag":"시작하기","count":49},{"language":"pt-BR","tag":"Primeiros passos","count":49},{"language":"ru","tag":"Начало работы","count":49},{"language":"zh-TW","tag":"快速入門","count":49},{"language":"en","tag":"Getting started","count":48},{"language":"zh-CN","tag":"快速入门","count":46},{"language":"en","tag":"Overview","count":41},{"language":"de","tag":"Agent SDK","count":36},{"language":"en","tag":"Setup and access","count":36},{"language":"es","tag":"Agent SDK","count":36},{"language":"id","tag":"Agent SDK","count":36},{"language":"it","tag":"Agent SDK","count":36},{"language":"jp","tag":"Agent SDK","count":36},{"language":"pt-BR","tag":"Agent SDK","count":36},{"language":"ru","tag":"Agent SDK","count":36},{"language":"zh-CN","tag":"Agent SDK","count":36},{"language":"zh-TW","tag":"Agent SDK","count":36},{"language":"de","tag":"Administration","count":34},{"language":"en","tag":"Administration","count":34},{"language":"es","tag":"Administración","count":34},{"language":"fr","tag":"Administration","count":34},{"language":"id","tag":"Administrasi","count":34},{"language":"it","tag":"Amministrazione","count":34},{"language":"jp","tag":"管理","count":34},{"language":"ko","tag":"관리","count":34},{"language":"pt-BR","tag":"Administração","count":34},{"language":"ru","tag":"Администрирование","count":34},{"language":"zh-CN","tag":"管理","count":34},{"language":"zh-TW","tag":"管理","count":34},{"language":"de","tag":"Plugins","count":32},{"language":"es","tag":"Plugins","count":32},{"language":"fr","tag":"SDK Agent","count":32},{"language":"fr","tag":"Plugins","count":32},{"language":"id","tag":"Plugin","count":32},{"language":"it","tag":"Plugin","count":32},{"language":"jp","tag":"プラグイン","count":32},{"language":"ko","tag":"Agent SDK","count":32},{"language":"ko","ta

## Source (plugins): https://docs.claude.com/en/docs/claude-code/plugins

Plugins overview - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
A Claude Code plugin is a directory of skills, agents, hooks, MCP servers, or other components that Claude Code installs and loads as one unit. Most plugins come from a marketplace, which is a catalog that lists plugins and where to fetch each one. You can also load a plugin from a folder someone gives you, or
build your own
.
These cases are covered on other pages:
You use claude.ai chat or Cowork and not Claude Code
: see
Plugins on claude.ai and in Cowork
You built an MCP server and want it in Anthropic’s directory
: see
Publish to the directory
You want Claude Code inside VS Code or a JetBrains IDE
: that’s the VS Code extension or the JetBrains plugin, not a Claude Code plugin. See
Use Claude Code in VS Code
or
JetBrains IDEs
To try a plugin now, run
/plugin
in a Claude Code terminal session and install one from the
Discover
tab, which lists the plugins from your marketplaces. From there:
Install and manage plugins
: the full install steps, scopes, and other surfaces
Create a plugin
: build your own
Decide whether you need a plugin
: whether a plugin is the right tool for what you want
​
Understand what a plugin is
A plugin is a directory of components, usually with a manifest. The manifest, a JSON file at
.claude-plugin/plugin.json
, gives the plugin its name and can add a version, a description, and other
metadata
. The components are what the plugin adds to Claude Code, such as:
Skills
:
SKILL.md
instructions Claude loads when relevant, and that you can also run as a command
Agents
: subagent definitions Claude can delegate to
Hooks
: commands Claude Code runs at points in its lifecycle, such as after every edit
A hooks module
: hooks written as JavaScript functions, which can also draw panes and add commands. A plugin that has one is called a mod. Some mods are
built into Claude Code
.
MCP servers
: tool servers Claude Code connects to while the plugin is enabled
This diagram shows a plugin named
my-plugin
that holds a skill, an agent, hooks, and an MCP server, and what you get from each file once the plugin loads.
For every component type a plugin can hold, with an example of each, see
Plugin components
. To see where each piece is located in a plugin’s directory, use the
plugin explorer
on that page.
​
Decide whether you need a plugin
Skills, subagents, hooks, and MCP servers all work on their own, without a plugin. A skill you save in
~/.claude/skills/
, for example, is available in every project on your machine. To set one up on its own, see
Skills
,
Subagents
,
Hooks
, or
MCP
.
Use a plugin when you want several skills, subagents, hooks, or MCP servers packaged as one unit. Install one to get a setup someone else built, with one command and updates from its marketplace. Make one to give your own setup to teammates, install it in many projects, or publish versioned releases.
​
What an enabled plugin adds to your sessions
An enabled plugin is part of every session, not only the sessions where you use it. That has a few consequences worth knowing before you install one:
Context and usage
: for each skill, agent, and command that
Claude can invoke on its own
, the name and description are in Claude’s context on every turn so that Claude knows it exists. Those tokens count toward your usage and leave less room in the
context window
even in sessions where nothing from the plugin runs. The full text of a skill or agent loads only when it’s used. What the plugin’s MCP servers add per turn follows
MCP tool search
.
Processes
: MCP servers the plugin defines run alongside each session where it’s enabled, and its hooks fire at their events.
Permissions
: what the plugin runs, it runs as you. See
Plugin security and trust
for what to review first.
You can check a plugin’s footprint at each stage:
Before you install
: open the plugin from the
Marketplaces
tab in
/plugin
. Plugins in Anthropic’s official marketplace show a
Context cost
estimate there.
After you install
:
Measure what a plugin costs
shows how to read a plugin’s footprint, and the
Installed
tab’s
Not used recently
group lists plugins you could turn off.
To stop it without uninstalling
: disable the plugin with
/plugin
or, in your shell,
claude plugin disable
. See
Manage installed plugins
.
​
Get plugins from a marketplace
A marketplace is a repository or directory with a
.claude-plugin/marketplace.json
file that lists plugins and where to fetch each one. It’s a catalog, not a hosted store. You add a marketplace once, then install plugins from it by name, such as
commit-commands@claude-plugins-official
.
A plugin marketplace isn’t
Claude Marketplace
. Claude Marketplace is the website at claude.com/marketplace where you browse plugins, connectors, partner products, and service partners. It isn’t a marketplace you add with
/plugin marketplace add
.
Claude Code adds Anthropic’s official marketplace the first time you start an interactive terminal session, unless a
managed policy
blocks it. Claude Code doesn’t add Anthropic’s community marketplace on its own. To distinguish Anthropic’s marketplaces, read
Anthropic’s marketplaces
. To see what the official one lists, open the
Discover
tab of
/plugin
in a session or browse
Claude Marketplace
.
This diagram shows the path from a marketplace to your session. A marketplace lists a plugin, you install that plugin, and Claude Code loads its components.
Install and manage plugins
has the install steps for each place you run Claude Code. While you’re developing a plugin, you don’t need a marketplace: load it straight from its folder with
--plugin-dir
, as
Develop without a marketplace
shows.
​
Make an installed plugin available in your session
Before a plugin you installed gives you a skill you can run, it has to be present at each of these layers:
Settings
: your settings list the marketplaces you’ve added and the plugins that are enabled.
Disk
:
~/.claude/plugins/
holds what Claude Code has fetched and installed.
Session
: plugins load at startup, or when you
reload plugins
.
Read
Plugin loading reference
for the rules at each layer, including which settings file takes precedence and where the files are on disk.
​
Tell Anthropic’s marketplaces from third-party ones
A marketplace’s name places it in one of three tiers. Claude Code accepts the official and community names only for marketplaces sourced from
github.com/anthropics/
repositories:
Official
: marketplaces with one of Anthropic’s
official marketplace names
, including
claude-plugins-official
and
claude-code-plugins
.
Community
: marketplaces with one of Anthropic’s community names, such as
claude-community
.
Identify Anthropic’s marketplaces by name
lists them.
Third-party
: every other marketplace. A marketplace your coworker or your organization publishes is third-party.
Whatever the tier, a plugin you install can run code with your user privileges. Read
Plugin security and trust
for how to review a plugin before you install it.
Through
managed settings
, an organization can allowlist or block marketplaces, force-install plugins, and turn off session-only loading. Read
Manage plugins for your organization
for those controls.
​
Understand install scopes
When you install a plugin, you pick a scope, and the scope decides who the plugin is enabled for:
User scope
: enabled for you in every project on this computer
Project scope
: enabled for everyone who works in this repository, through the committed
.claude/settings.json
. Each collaborator still
installs it on their own machine
Local scope
: enabled for you in this repository only
A plugin you install at user scope in the terminal, the desktop app’s local sessions, or the VS Code extension is available in the other two on that computer, because all three read the same settings files. See
Choose an install scope
for how to pick one.
A cloud session, including one in the browser at claude.ai/code, doesn’t load the plugins in your local settings. For install steps in the terminal, VS Code, and the desktop app, and for what a cloud session loads, see
Install a plugin
.
The same plugin format also installs on claude.ai and in Cowork, where a different set of components loads. For those surfaces, see
Plugins on claude.ai and in Cowork
on claude.com and its
component support table
.
​
Next steps
Most people start by installing a plugin from Anthropic’s official marketplace, which Claude Code adds the first time you start an interactive terminal session. Run
/plugin
in a terminal session to browse it, or follow
Install and manage plugins
, which also covers the desktop app and VS Code. To see what’s in that marketplace before you open Claude Code, browse
Claude Marketplace
on the web.
To build your own,
Create a plugin
starts with an empty directory and ends with a working plugin.
Once you’ve installed or built a plugin, these pages cover what comes next:
Share what you built
:
Publish and distribute a plugin
, through your own marketplace or
Anthropic’s directory
Check whether it works and is used
:
Test plugins with evals
and
Measure plugin cost and usage
Run a marketplace for your team
:
Create a marketplace
, then
Host and maintain a marketplace
Set plugin policy for an organization
:
Manage plugins for your organization
Fix a problem
:
Troubleshoot plugins
Was this page helpful?
Yes
No
{"docsConfig":{"theme":"mint","$schema":"https://mintlify.com/docs.json","name":"Claude Code Docs","description":"Official documentation for Claude Code, Anthropic's agentic coding tool available in the terminal, IDE, desktop app, and browser. Covers installation, configuration, skills, subagents, hooks, MCP, the Agent SDK, and reference material.","colors":{"primary":"#0E0E0E","light":"#D4A27F","dark":"#0E0E0E"},"logo":{"light":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/light.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=78fd01ff4f4340295a4f66e2ea54903c","dark":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/dark.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=1298a0c3b3a1da603b190d0de0e31712"},"favicon":"https://mintcdn.com/claude-code/T2WlxklWBkR5Y1mJ/favicon.ico?fit=max\u0026auto=format\u0026n=T2WlxklWBkR5Y1mJ\u0026q=85\u0026s=346a85952ae08d5ee90e3c34d4423930","appearance":{"default":"system"},"background":{"color":{"light":"#FDFDF7","dark":"#09090B"}},"navbar":{"links":[{"href":"https://platform.claude.com/","label":"Claude Developer Platform"}],"primary":{"type":"button","label":"Open Claude Code","href":"https://claude.ai/code"}},"footer":{"socials":{"x":"https://x.com/AnthropicAI","linkedin":"https://www.linkedin.com/company/anthropicresearch"},"links":[{"header":"Company","items":[{"label":"Anthropic","href":"https://www.anthropic.com/company"},{"label":"Careers","href":"https://www.anthropic.com/careers"},{"label":"Economic Futures","href":"https://www.anthropic.com/economic-futures"},{"label":"Research","href":"https://www.anthropic.com/research"},{"label":"News","href":"https://www.anthropic.com/news"},{"label":"Trust center","href":"https://trust.anthropic.com/"},{"label":"Transparency","href":"https://www.anthropic.com/transparency"}]},{"header":"Help and security","items":[{"label":"Availability","href":"https://www.anthropic.com/supported-countries"},{"label":"Status","href":"https://status.anthropic.com/"},{"label":"Support center","href":"https://support.claude.com/"}]},{"header":"Learn","items":[{"label":"Courses","href":"https://academy.claude.com/"},{"label":"MCP connectors","href":"https://claude.com/partners/mcp"},{"label":"Customer stories","href":"https://www.claude.com/customers"},{"label":"Engineering blog","href":"https://www.anthropic.com/engineering"},{"label":"Events","href":"https://www.anthropic.com/events"},{"label":"Powered by Claude","href":"https://claude.com/partners/powered-by-claude"},{"label":"Service partners","href":"https://claude.com/partners/services"},{"label":"Startups program","href":"https://claude.com/programs/startups"}]},{"header":"Terms and policies","items":[{"label":"Privacy choices","href":"https://www.anthropic.com/legal/privacy"},{"label":"Privacy policy","href":"https://www.anthropic.com/legal/privacy"},{"label":"Disclosure policy","href":"https://www.anthropic.com/responsible-disclosure-policy"},{"label":"Usage policy","href":"https://www.anthropic.com/legal/aup"},{"label":"Commercial terms","href":"https://www.anthropic.com/legal/commercial-terms"},{"label":"Consumer terms","href":"https://www.anthropic.com/legal/consumer-terms"}]}]},"seo":{"metatags":{"canonical":"https://code.claude.com/docs"}},"fonts":{"family":"Anthropic Sans"},"contextual":{"options":["copy","view","claude"],"display":"header"},"styling":{"latex":true},"navigation":{"languages":[{"language":"en","href":"en/overview"},{"language":"fr","href":"fr/overview"},{"language":"de","href":"de/overview"},{"language":"it","href":"it/overview"},{"language":"jp","href":"ja/overview"},{"language":"es","href":"es/overview"},{"language":"ko","href":"ko/overview"},{"language":"zh-CN","href":"zh-CN/overview"},{"language":"zh-TW","href":"zh-TW/overview"},{"language":"ru","href":"ru/overview"},{"language":"id","href":"id/overview"},{"language":"pt-BR","href":"pt/overview"}]}},"deployment":{"deploymentMetadataValue":{"subdomain":"claude-code","hasAudioNarration":false,"actualSubdomain":"claude-code","customDomains":["code.claude.com"],"gitSource":{"type":"github","owner":"anthropics","repo":"claude-code-docs","deployBranch":"main","contentDirectory":"","isPrivate":true,"mountPath":"","label":""},"chroma":{"liveDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85","collectionId":"5857522b-efb8-436a-af8d-9016a7b362b7","schemaVersion":"v3","latestBuiltDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85"},"feedback":{"thumbs":true},"entitlements":{"AI_CHAT":{"status":"ENABLED"},"REMOVE_BRANDING":{"status":"ENABLED"},"CONTEXTUAL_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"CODE_SNIPPET_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"WEB_MCP":{"status":"ENABLED"},"NARRATION":{"status":"ENABLED"}},"buildId":"6ae7a807e7a853c3110bf6c9","clientVersion":"0.0.4044","searchFilterCounts":[{"language":"en","tag":"Agent SDK","count":60},{"language":"en","tag":"Plugins","count":56},{"language":"de","tag":"Neuigkeiten","count":50},{"language":"en","tag":"What's New","count":50},{"language":"es","tag":"Novedades","count":50},{"language":"fr","tag":"Nouveautés","count":50},{"language":"it","tag":"Novità","count":50},{"language":"ko","tag":"새로운 기능","count":50},{"language":"pt-BR","tag":"Novidades","count":50},{"language":"ru","tag":"Что нового","count":50},{"language":"zh-TW","tag":"最新消息","count":50},{"language":"de","tag":"Erste Schritte","count":49},{"language":"es","tag":"Primeros pasos","count":49},{"language":"fr","tag":"Premiers pas","count":49},{"language":"id","tag":"Memulai","count":49},{"language":"it","tag":"Per iniziare","count":49},{"language":"jp","tag":"はじめに","count":49},{"language":"ko","tag":"시작하기","count":49},{"language":"pt-BR","tag":"Primeiros passos","count":49},{"language":"ru","tag":"Начало работы","count":49},{"language":"zh-TW","tag":"快速入門","count":49},{"language":"en","tag":"Getting started","count":48},{"language":"zh-CN","tag":"快速入门","count":46},{"language":"en","tag":"Overview","count":41},{"language":"de","tag":"Agent SDK","count":36},{"language":"en","tag":"Setup and access","count":36},{"language":"es","tag":"Agent SDK","count":36},{"language":"id","tag":"Agent SDK","count":36},{"language":"it","tag":"Agent SDK","count":36},{"language":"jp","tag":"Agent SDK","count":36},{"language":"pt-BR","tag":"Agent SDK","count":36},{"language":"ru","tag":"Agent SDK","count":36},{"language":"zh-CN","tag":"Agent SDK","count":36},{"language":"zh-TW","tag":"Agent SDK","count":36},{"language":"de","tag":"Administration","count":34},{"language":"en","tag":"Administration","count":34},{"language":"es","tag":"Administración","count":34},{"language":"fr","tag":"Administration","count":34},{"language":"id","tag":"Administrasi","count":34},{"language":"it","tag":"Amministrazione","count":34},{"language":"jp","tag":"管理","count":34},{"language":"ko","tag":"관리","count":34},{"language":"pt-BR","tag":"Administração","count":34},{"language":"ru","tag":"Администрирование","count":34},{"language":"zh-CN","tag":"管理","count":34},{"language":"zh-TW","tag":"管理","count":34},{"language":"de","tag":"Plugins","count":32},{"language":"es","tag":"Plugins","count":32},{"language":"fr","tag":"SDK Agent","count":32},{"language":"fr","tag":"Plugins","count":32},{"language":"id","tag":"Plugin","count":32},{"language":"it","tag":"Plugin","count":32},{"language":"jp","tag":"プラグイン","count":32},{"language":"ko","tag":"Agent SDK","count":32},{"language":"ko","tag":"플러그인","count":32},{"language":"pt-BR","tag":"Plugins","count":32},{"language":"ru","tag":"Плагины","count":32},{"language":"zh-CN","tag":"插件","count":32},{"language":"zh-TW","tag":"外掛","count":32},{"language":"en","tag":"Reference","count":28},{"language":"es","tag":"Configuración","count":28},{"language":"jp","tag":"設定","count":28},{"language":"zh-TW","tag":"設定","count":28},{"language":"de","tag":"Konfiguration","count":25},{"language":"en","tag":"Configuration","count":25},{"language":"fr","tag":"Configuration","count":25},{"language":"id","tag":"Konfigurasi","count":25},{"language":"id","tag":"Apa yang Baru","count":25},{"language":"id","tag":"Yang Baru","count":25},{"language":"it","tag":"Configurazione","count":25},{"language":"jp","tag":"新機能","count":25},{"language":"jp","tag":"最新情報","count":25},{"language":"ko","tag":"구성","count":25},{"language":"pt-BR","tag":"Configuração","count":25},{"language":"ru","tag":"Конфигурация","count":25},{"language":"zh-CN","tag":"配置","count":25},{"language":"zh-CN","tag":"新功能","count":25},{"language":"zh-CN","tag":"最新动态","count":25},{"language":"en","tag":"Settings","count":24},{"language":"de","tag":"Mit Claude Code entwickeln","count":22},{"language":"es","tag":"Crea con Claude Code","count":22},{"language":"fr","tag":"Développer avec Claude Code","count":22},{"language":"id","tag":"Membangun dengan Claude Code","count":22},{"language":"it","tag":"Crea con Claude Code","count":22},{"language":"jp","tag":"Claude Code で構築","count":22},{"language":"ko","tag":"Claude Code로 만들기","count":22},{"language":"pt-BR","tag":"Desenvolva com Claude Code","count":22},{"language":"ru","tag":"Разработка с Claude Code","count":22},{"language":"zh-CN","tag":"使用 Claude Code 构建","count":22},{"language":"zh-TW","tag":"使用 Claude Code 打造","count":22},{"language":"de","tag":"Referenz","count":20},{"language":"es","tag":"Referencia","count":20},{"language":"fr","tag":"Référence","count":20},{"language":"id","tag":"Referensi","count":20},{"language":"it","tag":"Riferimento","count":20},{"language":"jp","tag":"リファレンス","count":20},{"language":"ko","tag":"레퍼런스","count":20},{"language":"pt-BR","tag":"Referência","count":20},{"language":"ru","tag":"Справочник","count":20},{"language":"zh-CN","tag":"参考","count":20},{"language":"de","tag":"Plattformen und Integrationen","count":19},{"language":"es","tag":"Plataformas e integraciones","count":19},{"language":"fr","tag":"Plateformes et intégrations","count":19},{"language":"id","tag":"Platform dan integrasi","count":19},{"language":"it","tag":"Piattaforme e integrazioni","count":19},{"language":"jp","tag":"プラットフォームと連携","count":19},{"language":"ko","tag":"플랫폼 및 통합","count":19},{"language":"pt-BR","tag":"Plataformas e integrações","count":19},{"language":"ru","tag":"Платформы и интеграции","count":19},{"language":"zh-CN","tag":"平台与集成","count":19},{"language":"zh-TW","tag":"平台與整合","count":19},{"language":"de","tag":"Code-Review und Pull Requests","count":14},{"language":"es","tag":"Revisión de código y pull requests","count":14},{"language":"fr","tag":"Revue de code et pull requests","count":14},{"language":"it","tag":"Code review e pull request","count":14},{"language":"ko","tag":"코드 리뷰 및 풀 리퀘스트","count":14},{"language":"pt-BR","tag":"Revisão de código e pull requests","count":14},{"language":"ru","tag":"Код-ревью и pull request","count":14},{"language":"zh-TW","tag":"程式碼審查與 pull request","count":14},{"language":"zh-TW","tag":"部署","count":11}]},"assistantConfig":{"enableAskAiButton":false,"enableStarterQuestions":false,"enableAskAiSearchBar":true},"basePath":"/docs","hasChatPermissions":true,"hasWebMcpPermissions":true,"toggles":[{"name":"kill-isr","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"assistant-bash","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"chat-bucketing-batched","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"agent-mintlify-slack","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"agent-integrations-settings","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automations-pr-grouping","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"custom-prefix","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"analytics-v7","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"user-flows-analytics","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"no-publish-flow","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-onboarding","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"llms-txt-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"snapshot-serving-live","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"stripTemperatureMiddleware","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"support-platform-pylon-zendesk","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"snapshot-serving","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"instant-rollback","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"granular-notifications-server","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"granular-notifications","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automations-fable","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"fixed-ai-action-pricing","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automation-resolve-merge-conflict","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"scoped-publishing","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"mintql","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"page-level-analytics","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"editor-version-history-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"billing-page-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"full-page-search","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workspace-projects","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"assistant-v5","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"byok-sep-25","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"fork-pr-previews","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"revalidation-jwt","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"vite-origin","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"billing-updated-9-15","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-sso-scim","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"hobby-abuse-scan","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"dashboard-inbox","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-signup","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"turbopuffer-dual-write","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-enabled","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"approve-review-flow","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"sso-setup-deadline-banner","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false}],"googleFontsInlined":false},"customCss":[{"filePath":"button.css","content":".btn{position:relative;display:inline-flex;gap:.5rem;align-items:center;justify-content:center;flex-shrink:0;min-width:5rem;height:2.25rem;padding:.5rem 1rem;white-space:nowrap;font-family:Styrene;font-weight:600;border-radius:.5rem}"},{"filePath":"style.css","content":"@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-Regular-Static.otf) format(\"opentype\");font-weight:400;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-RegularItalic-Static.otf) format(\"opentype\");font-weight:400;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-Medium-Static.otf) format(\"opentype\");font-weight:500;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-MediumItalic-Static.otf) format(\"opentype\");font-weight:500;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-Semibold-Static.otf) format(\"opentype\");font-weight:600;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-SemiboldItalic-Static.otf) format(\"opentype\");font-weight:600;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-Bold-Static.otf) format(\"opentype\");font-weight:700;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-BoldItalic-Static.otf) format(\"opentype\");font-weight:700;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Serif Display\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Display-Regular-Static.otf) format(\"opentype\");font-weight:400;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif Display\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Display-RegularItalic-Static.otf) format(\"opentype\");font-weight:400;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Serif Display\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Display-Medium-Static.otf) format(\"opentype\");font-weight:500;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif Display\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Display-Semibold-Static.otf) format(\"opentype\");font-weight:600;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif Display\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Display-Bold-Static.otf) format(\"opentype\");font-weight:700;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-Regular-Static.otf) format(\"opentype\");font-weight:400;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-RegularItalic-Static.otf) format(\"opentype\");font-weight:400;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-Medium-Static.otf) format(\"opentype\");font-weight:500;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-MediumItalic-Static.otf) format(\"opentype\");font-weight:500;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-Semibold-Static.otf) format(\"opentype\");font-weight:600;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-SemiboldItalic-Static.otf) format(\"opentype\");font-weight:600;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-Bold-Static.otf) format(\"opentype\");font-weight:700;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-BoldItalic-Static.otf) format(\"opentype\");font-weight:700;font-style:italic;font-display:swap}:root{--always-white:0 0% 100%;--always-black:0 0% 0%;--constant-book-cloth:15 55% 80%;--constant-clay:15 60% 85%;--constant-kraft:25 40% 83%;--constant-manilla:40 20% 92%;--constant-slate-000:0 0% 100%;--constant-slate-050:48 33.3% 97.1%;--constant-slate-100:53 28.6% 94.5%;--constant-slate-150:48 25% 92.2%;--constant-slate-200:50 20.7% 88.6%;--constant-slate-250:51 16.5% 84.5%;--constant-slate-300:50 11.5% 79.6%;--constant-slate-350:50 9% 73.7%;--constant-slate-400:49 6.5% 66.9%;--constant-slate-450:48 4.8% 59.2%;--constant-slate-500:53 3.2% 51.4%;--constant-slate-550:51 3.1% 43.7%;--constant-slate-600:48 2.7% 35.9%;--constant-slate-650:48 3.4% 29.2%;--constant-slate-700:60 2.5% 23.3%;--constant-slate-750:60 2.1% 18.4%;--constant-slate-800:60 2.7% 14.5%;--constant-slate-850:30 3.3% 11.8%;--constant-slate-900:30 4% 9.8%;--constant-slate-950:60 2.6% 7.6%;--constant-slate-1000:60 3.4% 5.7%}:root:not(.dark){--accent-brand:15 63.1% 59.6%;--accent-main-000:15 55.6% 52.4%;--accent-main-100:15 55.6% 52.4%;--accent-main-200:15 63.1% 59.6%;--accent-main-900:0 0% 0%;--accent-pro-000:251 34.2% 33.3%;--accent-pro-100:251 40% 45.1%;--accent-pro-200:251 61% 72.2%;--accent-pro-900:253 33.3% 91.8%;--accent-secondary-000:210 73.7% 40.2%;--accent-secondary-100:210 70.9% 51.6%;--accent-secondary-200:210 70.9% 51.6%;--accent-secondary-900:211 72% 90%;--bg-000:0 0% 100%;--bg-100:48 33.3% 97.1%;--bg-200:53 28.6% 94.5%;--bg-300:48 25% 92.2%;--bg-400:50 20.7% 88.6%;--bg-500:50 20.7% 88.6%;--border-100:30 3.3% 11.8%;--border-200:30 3.3% 11.8%;--border-300:30 3.3% 11.8%;--border-400:30 3.3% 11.8%;--danger-000:0 61.4% 22.4%;--danger-100:0 58.6% 34.1%;--danger-200:0 58.6% 34.1%;--danger-900:0 50% 95%;--oncolor-100:0 0% 100%;--oncolor-200:60 6.7% 97.1%;--oncolor-300:60 6.7% 97.1%;--text-000:60 2.6% 7.6%;--text-100:60 2.6% 7.6%;--text-200:60 2.5% 23.3%;--text-300:60 2.5% 23.3%;--text-400:51 3.1% 43.7%;--text-500:51 3.1% 43.7%}:root.dark{--accent-brand:15 63.1% 59.6%;--accent-main-000:15 55.6% 52.4%;--accent-main-100:15 63.1% 59.6%;--accent-main-200:15 63.1% 59.6%;--accent-main-900:0 0% 0%;--accent-pro-000:251 84.6% 74.5%;--accent-pro-100:251 40.2% 54.1%;--accent-pro-200:251 40% 45.1%;--accent-pro-900:250 25.3% 19.4%;--accent-secondary-000:210 71.1% 62%;--accent-secondary-100:210 70.9% 51.6%;--accent-secondary-200:210 70.9% 51.6%;--accent-secondary-900:210 55.9% 24.6%;--bg-000:60 2.1% 18.4%;--bg-100:60 2.7% 14.5%;--bg-200:30 3.3% 11.8%;--bg-300:60 2.6% 7.6%;--bg-400:60 3.4% 5.7%;--bg-500:60 3.4% 5.7%;--border-100:51 16.5% 84.5%;--border-200:51 16.5% 84.5%;--border-300:51 16.5% 84.5%;--border-400:51 16.5% 84.5%;--danger-000:0 73.1% 66.5%;--danger-100:0 58.6% 34.1%;--danger-200:0 58.6% 34.1%;--danger-900:0 23% 15.6%;--oncolor-100:0 0% 100%;--oncolor-200:60 6.7% 97.1%;--oncolor-300:60 6.7% 97.1%;--text-000:48 33.3% 97.1%;--text-100:48 33.3% 97.1%;--text-200:50 9% 73.7%;--text-300:50 9% 73.7%;--text-400:48 4.8% 59.2%;--text-500:48 4.8% 59.2%}#home-header{font-family:\"Anthropic Sans\",system-ui,\"Segoe UI\",Roboto,Helvetica,Arial,sans-serif;font-weight:400!important;font-size:50px;line-height:1.2;margin-bottom:1rem;color:--text-000;display:flex;align-items:baseline;justify-content:center;flex-wrap:nowrap}#localization-select-trigger>:has(img[src*=flags]),div[id^=localization-select-item]>:has(img[src*=flags]){display:none}@media (min-width:768px){#home-header{justify-content:center}}.build-with{font-family:\"Anthropic Sans\",system-ui,\"Segoe UI\",Roboto,Helvetica,Arial,sans-serif;letter-spacing:-.02em}.claude-wordmark-wrapper{display:inline-flex;align-items:baseline;margin-left:10px}.claude-wordmark{height:40px;width:auto;position:relative}.dark #home-header,.dark .description-text{color:#fff}.description-text{color:#000}.dark .claude-wordmark{filter:invert(1)}:root{--bg-color:#f0efea}.dark{--bg-color:#2b2b2b}#category-select,#content-container,#table-of-contents,.dropdown-item,.eyebrow,body,input{font-family:\"Anthropic Sans\",system-ui,\"Segoe UI\",Roboto,Helvetica,Arial,sans-serif}.eyebrow{text-transform:uppercase;letter-spacing:.02rem}#content-container h1,#content-container h2,#content-container h3,#content-container h4,#content-container h5,#content-container h6{font-family:\"Anthropic Serif Display\",Georgia,\"Times New Roman\",Times,serif;font-weight:400;letter-spacing:0;word-spacing:.1em}#content-container p{font-size:1rem;line-height:1.65rem}.font-extrabold{font-weight:600!important}.wide-table{width:100%;overflow-x:auto}.wide-table table{width:175%;margin-bottom:0}#prompt-library-container{margin:4rem auto;max-width:48rem;padding-left:1.25rem;padding-right:1.25rem}.prompt-library-title{font-size:24px;text-align:center;font-weight:700;color:#1f2937}.dark .prompt-library-title{color:#e5e7eb}.prompt-library-description{margin-top:1rem;text-align:center}.main-content{margin-bottom:10rem;max-width:64rem;margin-left:auto;margin-right:auto;padding-left:1.25rem;padding-right:1.25rem}.prompt-controllers{display:flex;gap:.5rem}.prompt-search-container{position:relative;flex:1 1 0%}.prompt-search-icon-container{display:flex;position:absolute;top:0;bottom:0;left:0;align-items:center;padding-left:.75rem}.prompt-search-icon{margin-left:.25rem;margin-right:.75rem;flex:none;width:1rem;height:1rem;background-color:#6b7280;mask-image:url(https://mintlify.b-cdn.net/v6.5.1/solid/magnifying-glass.svg);mask-repeat:no-repeat;mask-position:center center}input.prompt-search-bar{display:block;height:2.5rem;padding-left:2.5rem;border-radius:.75rem;border-width:1px;background-color:#fff;width:100%;color:#111827;box-shadow:0 1px 2px 0 rgba(0,0,0,.05)}.dark input.prompt-search-bar{color:#fff;background-color:rgb(var(--background-dark));border-color:#d1d5db1a}input.prompt-search-bar:focus{outline-color:rgb(var(--primary))}.dark input.prompt-search-bar:focus{outline-color:rgb(var(--primary-light))}.dark .dropdown-icon,.dark .prompt-search-icon{background-color:#ffffff80}#category-select{padding-left:1rem;padding-right:2.5rem;height:2.5rem;display:flex;align-items:center;border-radius:.75rem;border-width:1px;color:#111827;background-color:#fff;cursor:pointer;box-shadow:0 1px 2px 0 rgba(0,0,0,.05);white-space:nowrap}.dark #category-select{background-color:rgb(var(--background-dark));border-color:#d1d5db1a;color:#fff}#category-select:hover,.dropdown-item:hover{background-color:#f9fafb}.dark #category-select:hover,.dark .dropdown-item:hover{background-color:#ffffff0d}#category-select:focus{outline-color:rgb(var(--primary))}.dark #category-select:focus{outline-color:rgb(var(--primary-light))}#categories-dropdown{top:calc(100% + 4px);padding:.5rem;display:none;position:absolute;z-index:10;border-radius:.75rem;border-width:1px;width:100%;color:#111827;background-color:#fff;box-shadow:0 1px 2px 0 rgba(0,0,0,.05)}.dark #categories-dropdown{background-color:rgb(var(--background-dark));border-color:#d1d5db1a;color:#fff}#categories-dropdown-clickout{position:fixed;top:0;right:0;bottom:0;left:0;z-index:0}.dropdown-icon-container{display:flex;position:absolute;top:0;bottom:0;right:0;align-items:center;padding-right:.25rem}.dropdown-icon{margin-left:.25rem;margin-right:.75rem;flex:none;width:.75rem;height:.75rem;background-color:#6b7280;mask-image:url(https://mintlify.b-cdn.net/v6.5.1/solid/caret-down.svg);mask-repeat:no-repeat;mask-position:center center}#prompts-container{grid-template-columns:repeat(1,minmax(0,1fr));gap:2rem;display:grid;margin-top:2.5rem}.dropdown-item{padding:.25rem .5rem;border-radius:.375rem;display:flex;align-items:center;cursor:pointer}.check-icon{mask-image:url(https://mintlify.b-cdn.net/v6.5.1/solid/check.svg);height:.875rem;width:1rem;background-color:rgb(var(--primary-light));mask-repeat:no-repeat;mask-position:center center}.prompt-card{margin:-.75rem;padding:.75rem;display:flex;border-radius:1rem}.prompt-card:hover{background-color:#03071208}.dark .prompt-card:hover{background-color:#ffffff08}.prompt-icon-container{display:flex;flex:none;align-items:center;justify-content:center;margin-right:1.5rem;border-radius:.75rem;height:4rem;width:4rem;background-color:#cb785c1a}.prompt-icon{height:1.5rem;width:1.5rem;background-color:rgb(var(--primary-light));mask-repeat:no-repeat;mask-position:center center}.prompt-title{color:rgb(31 41 55);font-weight:600}.dark .prompt-title{color:rgb(229 231 235)}.prompt-description{margin-top:.25rem}@media (min-width:640px){#category-select{width:16rem}}@media (min-width:1024px){#prompts-container{grid-template-columns:repeat(2,minmax(0,1fr))}}.home-cards-custom{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(2,auto);gap:1.5rem}.home-cards-custom .card{background:0 0;border:.5px solid hsl(var(--border-300));border-radius:12px;padding:.25rem}@media (max-width:1024px){.home-cards-custom{grid-template-columns:repeat(2,1fr);grid-template-rows:repeat(3,auto)}}@media (max-width:768px){.home-cards-custom{grid-template-columns:1fr;grid-template-rows:repeat(6,auto)}}.relative{position:relative}.flex-1{flex:1 1 0%}.mermaid{position:relative;background-color:#fdfdfb;background-image:linear-gradient(rgba(235,219,188,.25) 1px,transparent 1px),linear-gradient(90deg,rgba(235,219,188,.25) 1px,transparent 1px),linear-gradient(rgba(235,219,188,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(235,219,188,.1) 1px,transparent 1px);background-size:20px 20px,20px 20px,4px 4px,4px 4px;background-position:-1px -1px,-1px -1px,-1px -1px,-1px -1px;padding:20px;border-radius:8px;border:1px solid rgba(235,219,188,.4);box-shadow:0 2px 4px rgba(64,64,62,.08)}.dark .mermaid{background-color:#1a1918;background-image:linear-gradient(rgba(212,162,127,.15) 1px,transparent 1px),linear-gradient(90deg,rgba(212,162,127,.15) 1px,transparent 1px),linear-gradient(rgba(212,162,127,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(212,162,127,.08) 1px,transparent 1px);border:1px solid rgba(102,102,99,.5);box-shadow:0 2px 4px rgba(0,0,0,.2)}.digest-meta{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem 1rem;padding:.75rem 1rem;margin:1.5rem 0 2.5rem;border:1px solid hsl(var(--border-300)/.15);background:hsl(var(--bg-200));font-variant-numeric:tabular-nums;font-size:.875rem;color:hsl(var(--text-400))}#content-container .digest-meta a{color:hsl(var(--accent-main-100));font-weight:500;text-decoration:none;border-bottom:none}#content-container .digest-meta a:hover{text-decoration:underline}.digest-feature{position:relative;margin:2.5rem 0;padding:1.875rem 1.875rem 1.625rem;background:radial-gradient(circle,hsl(var(--text-000)/.025) 1px,transparent 1px) 0 0/18px 18px,linear-gradient(180deg,hsl(var(--constant-manilla)/.55),hsl(var(--constant-manilla)/.38));border:1px solid hsl(var(--border-300)/.12);box-shadow:inset 0 1px 0 hsl(var(--text-000)/.04),0 1px 2px hsl(var(--always-black)/.04)}.digest-feature::before{content:\"\";position:absolute;inset:0 auto 0 0;width:4px;background:hsl(var(--accent-brand))}.dark .digest-feature{background:radial-gradient(circle,hsl(var(--text-000)/.02) 1px,transparent 1px) 0 0/18px 18px,linear-gradient(180deg,hsl(var(--bg-000)/.75),hsl(var(--bg-000)/.5));border-color:hsl(var(--border-300)/.1);box-shadow:inset 0 1px 0 hsl(var(--text-000)/.03),0 1px 2px hsl(var(--always-black)/.25)}.digest-feature>:first-child{margin-top:0}.digest-feature>:last-child{margin-bottom:0}.digest-feature-header{display:flex;align-items:center;flex-wrap:wrap;gap:.625rem;margin:0 0 .75rem}#content-container .digest-feature-title{font-family:\"Anthropic Serif Display\",Georgia,serif;font-size:1.75rem;line-height:1.15;font-weight:500;letter-spacing:-.015em;color:hsl(var(--text-000));margin:0}#content-container .digest-feature-pill{font-family:ui-monospace,\"SF Mono\",Menlo,Consolas,monospace;font-size:.75rem;line-height:1;letter-spacing:.01em;padding:.3rem .6rem;border-radius:999px;background:hsl(var(--accent-brand)/.12);color:hsl(var(--accent-main-000));border:1px solid hsl(var(--accent-brand)/.25);white-space:nowrap;transform:translateY(1px)}#content-container .digest-feature-lede{font-size:1.0625rem;line-height:1.65;color:hsl(var(--text-100));margin:0 0 1.25rem;max-width:none}#content-container .digest-feature-lede code{font-size:.875em;padding:.1em .35em}#content-container .digest-feature-try{font-size:.875rem;color:hsl(var(--text-400));margin:1.25rem 0 .5rem}#content-container .digest-feature .frame{margin:1rem 0;border-radius:0;padding:0}#content-container .digest-feature .frame>*,#content-container .digest-feature [class*=CodeBlock],#content-container .digest-feature pre{border-radius:0}#content-container .digest-feature-link{display:inline-flex;align-items:center;gap:.35rem;font-size:.875rem;font-weight:500;color:hsl(var(--accent-main-100));text-decoration:none;border-bottom:none;margin-top:.75rem}#content-container .digest-feature-link::after{content:\"→\";transition:transform 120ms ease-out}#content-container .digest-feature-link:hover::after{transform:translateX(3px)}.digest-wins{margin:2.5rem 0;padding:1.5rem 1.75rem 1.25rem;background:hsl(var(--bg-200));border:1px solid hsl(var(--border-300)/.1)}.dark .digest-wins{background:hsl(var(--bg-200)/.6)}#content-container .digest-wins-title{font-family:\"Anthropic Serif Display\",Georgia,serif;font-size:1.25rem;font-weight:500;color:hsl(var(--text-000));margin:0 0 .75rem}.digest-wins-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));column-gap:2rem}#content-container .digest-wins-grid>div{position:relative;font-size:.875rem;line-height:1.5;color:hsl(var(--text-300));padding:.5rem 0 .5rem 1.125rem;border-top:1px solid hsl(var(--border-300)/.06);margin:0}#content-container .digest-wins-grid>div::before{content:\"+\";position:absolute;left:0;top:.5rem;font-family:ui-monospace,\"SF Mono\",Menlo,Consolas,monospace;font-size:.8125rem;font-weight:600;color:hsl(var(--accent-brand))}#content-container .digest-wins-grid>div:first-child,#content-container .digest-wins-grid>div:nth-child(2){border-top:none;padding-top:0}#content-container .digest-wins-grid>div:first-child::before,#content-container .digest-wins-grid>div:nth-child(2)::before{top:0}#content-container .digest-wins-grid code{font-size:.8125rem;padding:.1em .3em}:root{--toc-wrapper-max:92rem;--toc-wrapper-pad:2rem;--toc-col:19rem;--toc-side:28rem;--toc-btn-size:1.75rem}#toc-collapse-toggle{display:none;align-items:center;justify-content:center;position:fixed;top:10rem;right:calc(max((100% - var(--toc-wrapper-max))/2,0px) + var(--toc-wrapper-pad) + var(--toc-col) - var(--toc-btn-size) - .35rem);transition:right 200ms ease-out;z-index:30;width:var(--toc-btn-size);height:var(--toc-btn-size);border-radius:9999px;border:1px solid hsl(var(--border-300)/.15);background:hsl(var(--bg-100));color:hsl(var(--text-400));cursor:pointer}#toc-collapse-toggle:hover{background:hsl(var(--bg-300));color:hsl(var(--text-100))}#toc-collapse-toggle svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}#toc-collapse-toggle .toc-glyph{display:none;stroke-width:2}@media print{#toc-collapse-toggle{display:none!important}}@media (prefers-reduced-motion:reduce){#toc-collapse-toggle{transition:none}}@media (min-width:1280px){html:has(#table-of-contents-layout) #toc-collapse-toggle{display:flex}html.toc-collapsed #toc-collapse-toggle .toc-chevron{transform:rotate(180deg)}html.toc-collapsed #toc-collapse-toggle{right:.5rem;width:auto;padding:0 .5rem;gap:.25rem}html.toc-collapsed #toc-collapse-toggle .toc-glyph{display:block}html.toc-collapsed #table-of-contents-layout{display:none!important}html.toc-collapsed #content-side-layout:has(#table-of-contents-layout){display:none!important}html.toc-collapsed #content-container:has(#table-of-contents-layout) #content-area{width:100%!important}html.toc-collapsed #content-container:has(#table-of-contents-layout) #content-area>*{max-width:calc(var(--toc-wrapper-max) - var(--toc-side))}}@media (max-width:640px){.digest-feature{margin:1.5rem 0}#content-container .digest-feature-title{font-size:1.375rem}.digest-feature,.digest-wins{padding:1.25rem 1rem 1rem}.digest-wins-grid{grid-template-columns:1fr}#content-container .digest-wins-grid>div:nth-child(2){border-top:1px solid hsl(var(--border-300)/.06);padding-top:.5rem}#content-container .digest-wins-grid>div:nth-child(2)::before{top:.5rem}}[role=menu]:has(>.nav-dropdown-item){width:340px;max-width:calc(100vw - 32px);max-height:min(680px,calc(100vh - 130px));padding:8px;border-radius:16px}[role=menu]:has(>.nav-dropdown-item:nth-child(5)){width:640px;display:grid;grid-template-columns:1fr 1fr;column-gap:8px;align-content:start}.nav-dropdown-item{padding:9px 12px}.nav-dropdown-item span.text-sm{font-size:14.5px;font-weight:600;color:#141413}.nav-dropdown-item span.text-xs{font-size:13.5px;line-height:1.4;color:#73726c}.dark .nav-dropdown-item span.text-sm{color:#faf9f5}.dark .nav-dropdown-item span.text-xs{color:#97958c}@media (max-width:700px){[role=menu]:has(>.nav-dropdown-item:nth-child(5)){width:340px;display:block}}.nav-tabs .nav-tabs-item:focus-visible{outline:2px solid currentColor;outline-offset:-4px;border-radius:8px}#navigation-items button[aria-haspopup=menu]:not(#localization-select-trigger)~button[aria-haspopup=menu]{display:none}[data-base-ui-portal]:has(.nav-dropdown-item):has(~[data-base-ui-portal] .nav-dropdown-item){visibility:hidden;pointer-events:none}"}],"page":{"pagePath":"en/plugins/overview","slug":"/en/plugins/overview","pageMetadata":{"title":"Plugins overview","sidebarTitle":"Overview","description":"Understand what a Claude Code plugin is, when you need one instead of a standalone skill or MCP server, and which page to read to install or create one.","keywords":["plugin","plugins","plugin vs skill","plugin vs MCP","marketplace","what is a plugin","plugin store","sideload","Claude Marketplace"],"href":"/en/plugins/overview"},"description":{"compiledSource":"\"use strict\";\nconst {jsx: _jsx} = arguments[0];\nconst {useMDXComponents: _provideComponents} = arguments[0];\nfunction _createMdxContent(props) {\n  const _components = {\n    p: \"p\",\n    ..._provideComponents(),\n    ...props.components\n  };\n  return _jsx(_components.p, {\n    children: \"Understand what a Claude Code plugin is, when you need one instead of a standalone skill or MCP server, and which page to read to install or create one.\"\n  });\n}\nfunction MDXContent(props = {}) {\n  const {wrapper: MDXLayout} = {\n    ..._provideComponents(),\n    ...props.components\n  };\n  return MDXLayout ? _jsx(MDXLayout, {\n    ...props,\n    children: _jsx(_createMdxContent, {\n      ...props\n    })\n  }) : _createMdxContent(props);\n}\nreturn {\n  default: MDXContent\n};\n","frontmatter":{},"scope":{}},"pageType":"default","mdx":{"mdxSource":{"compiledSource":"\"use strict\";const{Fragment:_Fragment,jsx:_jsx,jsxs:_jsxs}=arguments[0];const{useMDXComponents:_provideComponents}=arguments[0];function _createMdxContent(props){const _components={

## Source (plugins-reference): https://docs.claude.com/en/docs/claude-code/plugins-reference

Plugin manifest reference - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
A plugin manifest is the
plugin.json
file in a plugin’s
.claude-plugin/
directory. It carries the plugin’s metadata and the
userConfig
values that Claude Code prompts the user for. It also declares any component that you define inline or keep outside its
default location
.
This reference is for plugin creators, and for marketplace owners who put component fields in a marketplace entry.
These cases are covered on other pages:
Learning to build a plugin
: start with
Create a plugin
What each component does at runtime
: see
Plugin components
Start at the section that matches what you’re looking up:
A field: the
Fields table
gives each field’s type, whether it’s required, its default, and what it accepts.
Path rules
covers the
./
prefix and containment for every component path
A
userConfig
option or a
channels
entry: the
User configuration
and
Channels
schemas
${CLAUDE_PLUGIN_ROOT}
or another variable a plugin can reference:
Environment variables
Where each component’s files go:
Standard layout
A message from
claude plugin validate
: the
troubleshooting page
lists each message with its fix and links to the relevant sections on this page
​
Manifest file
The manifest is optional. Without it, Claude Code loads the components it finds in the
standard layout
. The plugin name then comes from the marketplace entry, or from the directory name when you load the plugin with
--plugin-dir
.
Write a manifest when you want metadata, a component outside its default directory,
userConfig
, or an inline component definition.
Save the manifest at
.claude-plugin/plugin.json
under the plugin root. Put every other plugin file at the plugin root, not inside
.claude-plugin/
. That includes
skills/
,
commands/
, and
hooks/
.
The following example sets most of the keys in the
Fields table
. It passes validation in a plugin directory that contains each referenced path.
{
"name"
:
"deploy-tools"
,
"displayName"
:
"Deploy Tools"
,
"version"
:
"1.2.0"
,
"description"
:
"Deployment commands, a review agent, and a status monitor"
,
"author"
: {
"name"
:
"Example Team"
,
"email"
:
"dev@example.com"
,
"url"
:
"https://example.com"
},
"homepage"
:
"https://example.com/docs/deploy-tools"
,
"repository"
:
"https://github.com/example/deploy-tools"
,
"license"
:
"MIT"
,
"keywords"
: [
"deployment"
,
"ci"
],
"defaultEnabled"
:
true
,
"dependencies"
: [
"secrets-vault"
],
"metadata"
: {
"catalogId"
:
"cat-123"
},
"skills"
: [
"./extra-skills/"
],
"commands"
: {
"status"
: {
"source"
:
"./commands/status.md"
,
"description"
:
"Show the current deployment status"
},
"about"
: {
"content"
:
"Explain what the deploy-tools plugin provides."
,
"description"
:
"Describe this plugin"
}
},
"agents"
: [
"./agents/reviewer.md"
],
"hooks"
:
"./config/extra-hooks.json"
,
"mcpServers"
: {
"deploy-api"
: {
"command"
:
"node"
,
"args"
: [
"${CLAUDE_PLUGIN_ROOT}/server.js"
]
}
},
"lspServers"
:
"./.lsp.json"
,
"outputStyles"
:
"./styles/"
,
"experimental"
: {
"themes"
:
"./themes/"
,
"monitors"
:
"./config/monitors.json"
},
"userConfig"
: {
"api_token"
: {
"type"
:
"string"
,
"title"
:
"API token"
,
"description"
:
"Token for the deployment API"
,
"sensitive"
:
true
}
}
}
​
Unrecognized fields
An unrecognized top-level key is stripped, and an unrecognized key inside a
userConfig
option,
channels
entry,
lspServers
config, or
monitors
entry is rejected:
Top-level fields
: the field is stripped and the plugin loads.
claude plugin validate
reports each unrecognized top-level field as a warning
Strict objects
:
userConfig
options,
channels
entries,
lspServers
configs, and
monitors
entries are strict. An unknown key inside one is an error, and the plugin doesn’t load
​
Validate the manifest
claude plugin validate
is the authoritative check for a manifest. Run it from your shell against the plugin directory:
claude
plugin
validate
./my-plugin
The command reports one of these results:
Validation passed
: the manifest loads
Validation passed with warnings
: the manifest loads, but the validator found something to fix, such as an unknown top-level field that Claude Code strips, a
name
that isn’t kebab-case, or a missing
version
,
description
, or
author
. Pass
--strict
to turn warnings into failures in CI
Validation failed
: the manifest has a type mismatch, a path that is missing or escapes the plugin root, or an unknown key inside a
userConfig
option,
channels
entry,
lspServers
config, or
monitors
entry. Claude Code reports the same problem when it loads the plugin
The command also checks each MCP server entry the plugin declares in
.mcp.json
, in a
.json
file that
mcpServers
names, or inline in
plugin.json
. These MCP checks require Claude Code v2.1.281 or later and include:
Errors
: an entry Claude Code would drop when it loads the plugin, a
${user_config.KEY}
reference to an option the manifest doesn’t declare, and a remote
url
that isn’t a valid absolute URL
Warnings
: an
http://
or
ws://
URL to a non-loopback host, and a header value that looks like a literal credential
​
Fields
The table lists the top-level keys in
plugin.json
.
name
is the only required key. Where a field name is a link, the linked section has its full rules.
For component keys such as
commands
and
hooks
,
Component path forms
shows each accepted shape with an example, and every path follows the
path rules
for the
./
prefix, extensions, and containment.
Field
Type
Description
$schema
String
JSON Schema URL for editor autocomplete. Claude Code ignores it at load time
name
String
Plugin identifier, required. Use kebab-case. Every component is namespaced under it
displayName
String
Name shown in UI in place of
name
version
String
Version string. Setting it keeps users on that version until you change it
description
String
Short explanation of what the plugin provides
author
Object
name
, which is required, plus optional
email
and
url
homepage
String
Documentation URL. Must parse as a URL, or the plugin fails to load
repository
String
Source repository URL. Not validated
license
String
SPDX identifier such as
MIT
or
Apache-2.0
keywords
Array of strings
Discovery tags
metadata
Object
Free-form object for your own data. Claude Code doesn’t read it
icon
String
Icon for the plugin’s listing in Anthropic’s directory. Claude Code doesn’t read it
documentationUrl
String
Documentation link for the plugin’s listing in Anthropic’s directory. Claude Code doesn’t read it
supportUrl
String
Support link for the plugin’s listing in Anthropic’s directory. Claude Code doesn’t read it
privacyPolicyUrl
String
Privacy policy link for the plugin’s listing in Anthropic’s directory. Claude Code doesn’t read it
termsOfServiceUrl
String
Terms of service link for the plugin’s listing in Anthropic’s directory. Claude Code doesn’t read it
defaultEnabled
Boolean
Whether the plugin starts enabled when the user hasn’t set it. Defaults to
true
dependencies
Array of strings or objects
Plugins that must be enabled for this one to work
settings
Object
Settings Claude Code applies while the plugin is enabled. Only
agent
and
subagentStatusLine
take effect
userConfig
Object
Values Claude Code prompts the user for when the plugin is enabled
types
Path
A
.d.ts
file that declares the
$.state
values and
$
nouns of a
mod
channels
Array of objects
Message channels the plugin provides, each bound to one of its MCP servers
skills
Path, or array of paths
Directories to scan for skills, each a directory of
<name>/SKILL.md
folders or one folder holding
SKILL.md
directly.
"."
names the plugin root. Adds to the default
skills/
scan
commands
Path, array of paths, or object
Flat
.md
command files, directories of them, or an object map of command name to
source
or
content
. Replaces the default
commands/
scan
agents
Path, or array of paths
Agent
.md
files. Directories aren’t accepted. Replaces the default
agents/
scan
hooks
Path, object, or array of either
.json
hook files or inline hook config. Loaded together with
hooks/hooks.json
mcpServers
Path, object, or array of either
.json
MCP config files,
.mcpb
or
.dxt
bundles, or inline server configs keyed by name. Loaded together with
.mcp.json
; a server name declared later replaces an earlier one
lspServers
Path, object, or array of either
.json
LSP config files or inline server configs keyed by name. Loaded together with
.lsp.json
outputStyles
Path, or array of paths
Output style files or directories. Replaces the default
output-styles/
scan
workflows
Path, or array of paths
Workflow
.js
files or directories. Replaces the default
workflows/
scan
experimental
Object
Container for
themes
,
monitors
, and
evals
, whose manifest shape may still change
experimental.themes
Path, or array of paths
Theme files or directories. Replaces the default
themes/
scan. A top-level
themes
key still loads, with a
claude plugin validate
warning
experimental.monitors
Path, or inline array
A
.json
file holding the monitors array, or the array itself. Defaults to
monitors/monitors.json
. A top-level
monitors
key still loads, with a
claude plugin validate
warning. Monitors
don’t start with the
-p
flag
experimental.evals
Path, or array of paths
Directory that holds the plugin’s
eval cases
when it isn’t the default
evals/
.
claude plugin eval --eval-dir
overrides it
In the Type column, a path is a string relative to the plugin root, such as
"./custom/commands"
.
​
name
The plugin identifier. It must be non-empty, with no spaces,
@
,
:
, path separators, control characters, or bidirectional-formatting characters; use kebab-case.
Claude Code namespaces every component under it, so an agent
reviewer
in plugin
deploy-tools
appears as
deploy-tools:reviewer
.
claude plugin validate
also checks that the name doesn’t pass as one of Anthropic’s own plugins. The check ignores case and treats any run of separators as one:
Name
Result
Starts with
claude-
,
anthropic-
,
anthropics-
, or
cc-plugin-
Error
Is
claude
,
anthropic
,
anthropics
,
claude-code
, or
claude-mods
Error
Puts
official
beside
claude
or
anthropic
, such as
official-claude-tools
Error
Has
claude
,
anthropic
, or
anthropics
as a whole word anywhere else, such as
mcp-for-claude
Warning
The error reads
Plugin name "<name>" is reserved: it passes as one of Anthropic's own
, and the warning reads
Plugin name "<name>" reads as one of Anthropic's own
.
claude plugin init
and
claude plugin tag
refuse a name that draws the error. Claude Code still installs and loads a plugin whose name they refuse.
​
displayName
The name shown in UI in place of
name
. It may contain spaces and any casing, and it isn’t used for namespacing or lookup.
For a marketplace-installed plugin, a
displayName
on the
marketplace entry
takes precedence over this value.
​
version
A version string, not checked against semver. Setting it pins the plugin to that version until you change it; see
Versions and updates
. A plugin with a
command
source
, a plugin from a
marketplace hosted on claude.ai
, and a plugin
loaded in place
from a marketplace added from a local path aren’t pinned by this field.
​
metadata
A free-form object for your own data, such as catalog or entitlement fields. Claude Code doesn’t read it. Requires Claude Code v2.1.222 or later.
​
Directory listing fields
Anthropic’s directory reads the
icon
,
documentationUrl
,
supportUrl
,
privacyPolicyUrl
, and
termsOfServiceUrl
fields from
plugin.json
for your plugin’s listing when you
submit the plugin
. Claude Code ignores them at load time. Set them only in
plugin.json
. In a
marketplace entry
,
claude plugin validate
reports each one as an unknown field.
Set
icon
to the path of an image file inside the plugin, such as
./logo.png
, and each of the four URL fields to an
https://
URL.
claude plugin validate
doesn’t report these fields in
plugin.json
as unknown on Claude Code v2.1.281 or later. Earlier versions print an
Unknown field
warning for each one, so a
--strict
run fails on those versions.
​
defaultEnabled
Whether the plugin starts enabled when the user hasn’t set it in
enabledPlugins
. Defaults to
true
. A plugin that an enabled plugin depends on starts enabled regardless. The same field in the marketplace entry overrides this one.
Once a user’s
enabledPlugins
entry is written, it persists across plugin updates, so changing
defaultEnabled
in a later release doesn’t change the setting for an existing user.
​
dependencies
Plugins that must be enabled for this one to work. Each entry is
"name"
,
"name@marketplace"
, or
{ "name": "...", "marketplace": "...", "version": "..." }
. Bare names resolve against this plugin’s own marketplace. See
dependency constraints
.
​
settings
Settings Claude Code applies while the plugin is enabled. Only
agent
and
subagentStatusLine
take effect; other keys are dropped at load. A
settings.json
at the plugin root takes precedence over this key. See
Default settings
.
​
Component path forms
Every component key accepts a path relative to the plugin root.
hooks
,
mcpServers
,
lspServers
, and
experimental.monitors
also accept inline configuration,
commands
also accepts an object map, and
mcpServers
also accepts MCP bundle paths and URLs. The examples that follow show each accepted shape once. For what each component does at runtime, see
Plugin components
.
​
Path-only fields
agents
,
skills
,
outputStyles
,
workflows
, and
experimental.themes
take one path or an array of paths.
agents
entries must be
.md
files, and
skills
entries must be directories. The other three accept a directory or a file.
{
"agents"
: [
"./custom-agents/reviewer.md"
,
"./custom-agents/tester.md"
],
"skills"
: [
"./extra-skills/"
,
"."
],
"outputStyles"
:
"./styles/"
}
​
commands
commands
takes a path, an array of paths, or an object map. A path names a flat
.md
command file or a directory. In the object map, each key becomes the command name after the plugin prefix. For example,
"about"
in plugin
deploy-tools
runs as
/deploy-tools:about
.
Each value sets exactly one of
source
or
content
, and an entry that sets both or neither fails validation. The other fields in this table are optional:
Field
Type
Description
source
string
Path to the command’s Markdown file, relative to the plugin root
content
string
Inline Markdown for the command body, instead of
source
description
string
Description shown for the command
argumentHint
string
Argument hint shown after the command name, such as
[file]
model
string
Default model for the command
allowedTools
array of strings
Tools the command may use without prompting
This map declares one command from a file and one from inline content:
{
"commands"
: {
"status"
: {
"source"
:
"./commands/status.md"
,
"argumentHint"
:
"[env]"
},
"about"
: {
"content"
:
"Explain what this plugin provides."
}
}
}
​
hooks
hooks
takes a
.json
file path, an inline hooks object in the same shape as
hooks
in
settings.json
, or an array mixing both. For hook events and handler fields, see the
hooks reference
.
A hooks file wraps the event map in a top-level
"hooks"
key, the shape
hooks/hooks.json
uses. A file that contains only the event map, without that wrapper, fails to load. An inline object is the event map itself, with no wrapper.
Claude Code merges whatever you declare with
hooks/hooks.json
when that file exists. This array loads one hooks file and declares one inline
PostToolUse
hook:
{
"hooks"
: [
"./config/extra-hooks.json"
,
{
"PostToolUse"
: [
{
"matcher"
:
"Write|Edit"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"
\"
${CLAUDE_PLUGIN_ROOT}
\"
/scripts/format.sh"
}
]
}
]
}
]
}
The file that array names carries the
"hooks"
wrapper around its own event map:
config/extra-hooks.json
{
"hooks"
: {
"PreToolUse"
: [
{
"matcher"
:
"Bash"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"
\"
${CLAUDE_PLUGIN_ROOT}
\"
/scripts/check-command.sh"
}
]
}
]
}
}
​
mcpServers
mcpServers
takes a
.json
file path, an MCP bundle path or URL, an inline map, or an array mixing them. For server config fields, see
plugin-provided MCP servers
.
Claude Code loads
.mcp.json
at the plugin root first, then each declared shape in order. A server name declared later replaces an earlier one.
An
mcpServers
value takes one of these shapes:
Shape
Example value
What Claude Code does
.json
file path
"./mcp/servers.json"
Reads the file as an
mcpServers
map
MCP bundle path
"./bundle.mcpb"
Extracts the
.mcpb
or
.dxt
bundle into
.mcpb-cache/
under the plugin root and reads its server config
MCP bundle URL
"https://example.com/server.mcpb"
Downloads the bundle into
.mcpb-cache/
, then reads it
Inline map
{ "deploy-api": { "command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/server.js"] } }
Uses the map as server configs keyed by name
A bundle path or URL must end in
.mcpb
or
.dxt
. Any other extension fails validation.
​
lspServers
lspServers
takes a
.json
file path, an inline map of server name to config, or an array of either.
Claude Code loads
.lsp.json
at the plugin root first, then each declared config in order. A server name declared later replaces an earlier one.
Each server config is a strict object with these fields. An unknown key fails validation.
Field
Required
Description
command
Yes
Language server binary. No spaces unless the value starts with
/
; put arguments in
args
extensionToLanguage
Yes
Map of file extension to LSP language ID, at least one entry. Keys start with a dot, such as
".go"
args
No
Arguments passed to the server
transport
No
Communication transport:
stdio
(default) or
socket
. Claude Code accepts
socket
but runs every server over stdio, so the stdout protocol rules apply to all servers
env
No
Environment variables for the server process
initializationOptions
No
Options sent in the initialize request
settings
No
Settings sent by
workspace/didChangeConfiguration
workspaceFolder
No
Workspace folder path for the server
startupTimeout
No
Milliseconds to wait for startup, a positive integer
shutdownTimeout
No
Milliseconds to wait for a graceful shutdown, a positive integer. When the timeout elapses, Claude Code terminates the server process. When unset, no timeout applies
requestTimeout
No
Milliseconds to wait for the server to answer a request, a positive integer. Defaults to
60000
, so a request the server never answers fails after 60 seconds. Requires v2.1.288 or later
restartOnCrash
No
Whether to restart the server after it crashes. Defaults to
true
. Set to
false
to leave a crashed server stopped instead of restarting it
maxRestarts
No
Restart attempts before giving up, zero or more
diagnostics
No
Whether to push diagnostics into context after edits. Defaults to
true
This inline config runs
gopls
for
.go
files:
{
"lspServers"
: {
"go"
: {
"command"
:
"gopls"
,
"args"
: [
"serve"
],
"extensionToLanguage"
: {
".go"
:
"go"
}
}
}
}
For the language servers Anthropic publishes as plugins and how the servers behave at runtime, see
Code intelligence
.
​
monitors
experimental.monitors
takes a
.json
file path or the inline array. When you omit the key, Claude Code loads
monitors/monitors.json
if it exists.
Each entry is a strict object with these fields.
Field
Required
Description
name
Yes
Identifier unique within the plugin
command
Yes
Shell command Claude Code runs as a persistent background process in the session working directory
description
Yes
Short summary shown in the task panel and notification summaries
when
No
With
"always"
, the default, the monitor starts at session start and on plugin reload. With
"on-skill-invoke:<skill>"
, it starts the first time that skill runs
This inline array declares one monitor that starts the first time the
deploy
skill runs:
{
"experimental"
: {
"monitors"
: [
{
"name"
:
"deploy-status"
,
"command"
:
"
\"
${CLAUDE_PLUGIN_ROOT}
\"
/scripts/poll-deploy.sh"
,
"description"
:
"Deployment status changes"
,
"when"
:
"on-skill-invoke:deploy"
}
]
}
}
A monitor
command
can’t reference
${user_config.*}
. See
Fields that run through a shell
.
​
Path rules
Every component path in a manifest is relative to the plugin root and must start with
./
. A path such as
commands/foo.md
fails validation.
skills
and
mcpServers
each accept one form outside that rule:
skills
: also accepts
"."
. Both
"."
and
"./"
denote the plugin root. Before v2.1.221,
"."
failed manifest validation, so use
"./"
when the plugin must load on earlier versions
mcpServers
: also accepts an
https://
bundle URL
experimental.evals
isn’t a component path, so the rules in this section don’t cover it, and
claude plugin eval
checks the value when it runs instead. It names a directory below the plugin root, such as
"quality/evals"
, with or without the
./
prefix. With an array, only the first entry is used. For what the value accepts and what happens with an unusable one, see
Use a different eval directory
.
​
Containment and existence
Every component path must resolve inside the plugin root and must exist.
claude plugin validate
checks the paths under every component key:
Containment
: a path that resolves outside the plugin root doesn’t load, and the
/plugin
Errors
tab shows
<component> path escapes plugin directory: <path>
. A path containing
..
is the usual case, and
claude plugin validate
reports the error
Path contains ".." which could be a path traversal attempt
Existence
: a path that doesn’t exist doesn’t load, and the
/plugin
Errors
tab shows
<component> path not found: <path>
.
claude plugin validate
reports the error
Path not found
For
outputStyles
,
lspServers
,
monitors
, and
themes
paths, the
claude plugin validate
check requires Claude Code v2.1.283 or later.
​
How each key combines with its default location
Each component key either replaces its default location, adds to it, or merges with it:
Replaces the default
:
commands
,
agents
,
outputStyles
,
workflows
,
experimental.themes
,
experimental.monitors
. When you set
commands
, the default
commands/
directory isn’t scanned. To keep the default and add more, list it explicitly:
"commands": ["./commands/", "./extras/"]
Adds to the default
:
skills
. The
skills/
directory is still scanned, and the listed directories load alongside it
Merges
:
hooks
,
mcpServers
,
lspServers
. The default file loads first, and what the manifest declares merges into it, as described under
Component path forms
If a plugin has a default folder such as
commands/
and also sets the manifest key that replaces it, Claude Code loads the manifest paths and not the folder.
claude plugin list
and the
/plugin
interface then show the warning
Default <folder>/ folder is ignored because the manifest sets "<key>"
.
To avoid the warning, set the key to a path inside that folder:
"commands": ["./commands/deploy.md"]
names a file in the default folder and produces no warning.
​
User configuration
userConfig
declares values Claude Code prompts the user for when the plugin is enabled, so users don’t edit
settings.json
themselves.
Keys are identifiers made of letters, digits, and underscores, and can’t start with a digit.
Each value is a strict object with these fields. An unknown key fails validation.
Field
Required
Description
type
Yes
One of
string
,
number
,
boolean
,
directory
, or
file
title
Yes
Label shown in the configuration dialog
description
Yes
Help text shown beneath the field
required
No
If
true
, the configuration dialog doesn’t accept an empty value
default
No
Value used when the user provides nothing: a string, number, boolean, or array of strings
options
No
For
string
, the values the field accepts, shown as a picker in
/config
. See
Limit a field to fixed options
. Requires Claude Code v2.1.271 or later
multiple
No
For
string
, allows an array of strings
sensitive
No
If
true
, masks input and stores the value in secure storage instead of
settings.json
min
/
max
No
Bounds for
number
Each option of each enabled plugin also appears as a row in the
/config
panel, except
sensitive
options and
multiple
lists. The
/config
rows require Claude Code v2.1.269 or later.
This
userConfig
declares an endpoint and a masked token:
{
"userConfig"
: {
"api_endpoint"
: {
"type"
:
"string"
,
"title"
:
"API endpoint"
,
"description"
:
"Your team's API endpoint"
},
"api_token"
: {
"type"
:
"string"
,
"title"
:
"API token"
,
"description"
:
"API authentication token"
,
"sensitive"
:
true
}
}
}
​
Limit a field to fixed options
Set
options
on a
userConfig
field to make users pick its value from a fixed list.
To limit a
tone
field to three options, list them in
options
and set
default
to one of them:
{
"userConfig"
: {
"tone"
: {
"type"
:
"string"
,
"title"
:
"Tone"
,
"description"
:
"Voice for generated replies"
,
"options"
: [
"neutral"
,
"warm"
,
"formal"
],
"default"
:
"neutral"
}
}
}
If you declare
options
on any field, users on Claude Code versions before v2.1.271 can’t load the plugin.
options
applies to a
string
field that isn’t
multiple
or
sensitive
. Set
default
to one of the listed values, or set
required: true
so the user must pick one. Each option is a plain label of 1 to 64 characters, and
claude plugin validate
, which you run in your shell, reports anything else it rejects. A plugin whose
options
break these rules fails to load.
​
Where values are stored
Non-sensitive values are saved under
pluginConfigs
in the user’s
settings.json
. Sensitive values go to the platform’s secure credential store instead. The
settings page
lists which settings files
pluginConfigs
is read from.
​
Reference a saved value
Reference a saved value where the plugin needs it, in one of two forms:
${user_config.KEY}
: substituted in MCP server config, LSP server config,
exec-form
hook
args
, and skill and agent content. In skill and agent content, only non-sensitive values are substituted, and a sensitive value there becomes a placeholder
CLAUDE_PLUGIN_OPTION_<KEY>
: exported to hook processes for every option, with
<KEY>
uppercased. A shell-form hook reads
$CLAUDE_PLUGIN_OPTION_API_TOKEN
for
api_token
​
Fields that run through a shell
Shell-form hook commands, monitor commands, and MCP
headersHelper
reject
${user_config.*}
. A component that references it in one of these fields fails with an
error
instead of running, because the field’s value is passed to a shell that would re-parse the substituted value.
The table shows how the value can reach each of these fields instead.
Field
How the value can reach it
Shell-form hook commands
Use
exec form
with
args
, or read
CLAUDE_PLUGIN_OPTION_<KEY>
from the hook’s environment
Monitor commands
Not through Claude Code. Monitor processes don’t receive
CLAUDE_PLUGIN_OPTION_<KEY>
, so the monitor script has to obtain the value on its own
MCP
headersHelper
Not through Claude Code. The helper’s environment carries
CLAUDE_PLUGIN_ROOT
,
CLAUDE_CODE_MCP_SERVER_NAME
, and
CLAUDE_CODE_MCP_SERVER_URL
but no option values, so the helper script has to obtain the value on its own
​
Channels
channels
declares the message channels a plugin provides, such as a bridge to a chat app. When you declare one, Claude Code can prompt for the channel’s configuration when the plugin is enabled. For how the server injects messages, see the
channels reference
.
Each entry is a strict object bound to one of the plugin’s MCP servers, with these fields:
Field
Required
Description
server
Yes
Key of the MCP server in this plugin’s
mcpServers
that the channel binds to
displayName
No
Name shown in the configuration dialog title. Defaults to the server name
userConfig
No
Options to prompt for, in the same shape as
top-level
userConfig
. Saved values substitute into
${user_config.KEY}
references in the server’s
env
This manifest binds a channel to the plugin’s
telegram
MCP server and prompts for a bot token that substitutes into the server’s
env
:
{
"mcpServers"
: {
"telegram"
: {
"command"
:
"node"
,
"args"
: [
"${CLAUDE_PLUGIN_ROOT}/server.js"
],
"env"
: {
"BOT_TOKEN"
:
"${user_config.bot_token}"
}
}
},
"channels"
: [
{
"server"
:
"telegram"
,
"displayName"
:
"Telegram"
,
"userConfig"
: {
"bot_token"
: {
"type"
:
"string"
,
"title"
:
"Bot token"
,
"description"
:
"Telegram bot token"
,
"sensitive"
:
true
}
}
}
]
}
​
Environment variables
Claude Code provides three path variables to plugin components. Reference them as
${NAME}
in the fields listed under
Where each variable resolves
, and read them as environment variables in the processes that receive them.
Variable
Resolves to
Use it for
${CLAUDE_PLUGIN_ROOT}
Absolute path of the plugin’s installed version
Scripts, binaries, and config files bundled with the plugin
${CLAUDE_PLUGIN_DATA}
~/.claude/plugins/data/<id>/
, created on first reference and kept across plugin updates.
<id>
is the plugin identifier with every character other than a letter, digit,
_
, or
-
replaced by
-
Installed dependencies such as
node_modules
, generated code, and caches
${CLAUDE_PROJECT_DIR}
The project root
Project-local scripts and config files
${CLAUDE_PLUGIN_ROOT}
changes when the plugin updates, so don’t write state there. For where the root moves and when the old directory is cleaned up, see the
loading page
.
By default, Claude Code deletes the
${CLAUDE_PLUGIN_DATA}
directory when you uninstall the plugin from the last place it’s installed. For
--keep-data
and the other cases where it stays, see
plugin uninstall
.
​
Where each variable resolves
In each plugin component,
${...}
references resolve inline in specific fields, and some components also receive the variables in their process environment:
Plugin component
Fields where
${...}
resolves
Exported to the process
Hook commands
Anywhere in
command
and
args
CLAUDE_PLUGIN_ROOT
,
CLAUDE_PLUGIN_DATA
,
CLAUDE_PROJECT_DIR
, and
CLAUDE_PLUGIN_OPTION_<KEY>
Monitor commands
Anywhere in
command
Not exported
MCP
stdio
servers
command
,
args
,
env
CLAUDE_PLUGIN_ROOT
,
CLAUDE_PLUGIN_DATA
MCP
http
,
sse
,
ws
servers
url
,
headers
,
headersHelper
Not applicable
LSP servers
command
,
args
,
env
,
workspaceFolder
CLAUDE_PLUGIN_ROOT
,
CLAUDE_PLUGIN_DATA
,
CLAUDE_PROJECT_DIR
Skill, command, and agent content
Anywhere in the Markdown body
Not applicable
The variables aren’t present in the environment of commands Claude runs through the Bash tool, in the main session or in a subagent. In skill, command, and agent content, write the
${...}
reference in the Markdown body instead, and Claude Code substitutes the path inline when it loads the content.
​
Quoting and path separators
Keep each substituted path a single argument:
Hook commands
: use
exec form
with
args
so each path is one argument with no quoting
Shell-form hooks and monitor commands
: wrap the variable in double quotes so a path with spaces stays one word
If you leave one of these variables outside quotes in a shell-form command in a hooks file,
claude plugin validate
warns about it unless the hook sets
shell
to
"powershell"
.
This shell-form hook runs a script bundled with the plugin:
{
"hooks"
: {
"PostToolUse"
: [
{
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"
\"
${CLAUDE_PLUGIN_ROOT}
\"
/scripts/process.sh"
}
]
}
]
}
}
On Windows, most substituted paths use forward slashes, as in
C:/Users/you/...
. They keep their native backslashes in an
exec-form hook
and in a hook that runs through PowerShell, which is the default shell on Windows when Git Bash isn’t installed.
​
Standard layout
Each component type has a default location under the plugin root, used when the manifest doesn’t point elsewhere.
Component
Default location
Contents
Manifest
.claude-plugin/plugin.json
Plugin metadata and configuration. Optional
Skills
skills/
One
<name>/SKILL.md
per skill. A plugin with
SKILL.md
at its root, no
skills/
, and no
skills
key loads as a single skill
Commands
commands/
Flat Markdown command files. Prefer
skills/
for new plugins
Agents
agents/
Agent Markdown files. Subfolders are part of the
agent name
Hooks
hooks/hooks.json
Hook configuration
MCP servers
.mcp.json
MCP server definitions
LSP servers
.lsp.json
LSP server configurations
Output styles
output-styles/
Output style Markdown files
Workflows
workflows/
Workflow
.js
files
Themes
themes/
Theme JSON files
Monitors
monitors/monitors.json
The monitors array
Executables
bin/
Files here are on the Bash tool’s
PATH
while the plugin is enabled, so Claude runs them as bare commands. claude.ai and Cowork don’t install a plugin that has this directory, including one you
distribute through claude.ai organization settings
Settings
settings.json
agent
and
subagentStatusLine
defaults applied while the plugin is enabled
A plugin that uses every default location, plus a
scripts/
folder that its hooks call, is laid out like this:
deploy-tools/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── deploy/
│       └── SKILL.md
├── commands/
│   └── status.md
├── agents/
│   └── reviewer.md
├── hooks/
│   └── hooks.json
├── monitors/
│   └── monitors.json
├── output-styles/
│   └── terse.md
├── themes/
│   └── dracula.json
├── workflows/
│   └── release-audit.js
├── bin/
│   └── deploy-tool
├── scripts/
│   └── format.sh
├── settings.json
├── .mcp.json
└── .lsp.json
To click through this layout and read what each file does, open the
plugin explorer
.
A
CLAUDE.md
at the plugin root isn’t loaded as context, and
claude plugin validate
warns when it finds one. To include instructions that load into Claude’s context, put them in a skill.
​
Marketplace entries and the manifest
A
marketplace entry
accepts
its own fields
, including
strict
, and every field on this page except the
directory listing fields
.
The
strict
field decides whether the entry may add components to a plugin that has its own
plugin.json
. It defaults to
true
.
​
How entry fields combine with
plugin.json
The entry either serves as the manifest, adds components to it, or conflicts with it:
No
plugin.json
: the entry is the manifest, regardless of
strict
. Entry
hooks
loads only in the inline object form. For a file path or array there, the
/plugin
Errors
tab shows a
not yet supported in a marketplace entry
error
plugin.json
present,
strict
unset or
true
: Claude Code loads the manifest and appends the entry’s
commands
,
agents
,
skills
,
outputStyles
, and
themes
to it. For
hooks
, the entry’s matchers for an event replace the manifest’s matchers for that same event, and events only the manifest declares keep theirs
plugin.json
present,
strict: false
: an entry that declares any of
commands
,
agents
,
skills
,
hooks
,
outputStyles
, or
themes
is a conflict, and the plugin fails to load with
Plugin <name> has conflicting manifests
When a
marketplace entry whose
source
is the marketplace root
lists specific
skills
subdirectories, only those subdirectories load, and the plugin’s default
skills/
directory isn’t scanned. A
skills
key in the manifest instead
adds to the default
.
​
Metadata precedence
Some metadata fields have a fixed precedence regardless of
strict
:
defaultEnabled
and display fields
: the entry’s
defaultEnabled
and its
display fields
such as
displayName
override the manifest’s
version
: the manifest’s
version
overrides the entry’s
name
: when the entry lists the plugin under a different
name
than the manifest,
enabledPlugins
uses the entry name, and components are namespaced under the manifest name
For the full precedence table, see
Strict mode
.
​
Next steps
Add components to a plugin
: what each component does at runtime, with an example that validates
Marketplace reference
: the entry fields a marketplace can set for your plugin
Plugin commands reference
:
claude plugin validate
flags and output
Troubleshoot plugins
: each validation message with its fix
Was this page helpful?
Yes
No
{"docsConfig":{"theme":"mint","$schema":"https://mintlify.com/docs.json","name":"Claude Code Docs","description":"Official documentation for Claude Code, Anthropic's agentic coding tool available in the terminal, IDE, desktop app, and browser. Covers installation, configuration, skills, subagents, hooks, MCP, the Agent SDK, and reference material.","colors":{"primary":"#0E0E0E","light":"#D4A27F","dark":"#0E0E0E"},"logo":{"light":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/light.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=78fd01ff4f4340295a4f66e2ea54903c","dark":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/dark.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=1298a0c3b3a1da603b190d0de0e31712"},"favicon":"https://mintcdn.com/claude-code/T2WlxklWBkR5Y1mJ/favicon.ico?fit=max\u0026auto=format\u0026n=T2WlxklWBkR5Y1mJ\u0026q=85\u0026s=346a85952ae08d5ee90e3c34d4423930","appearance":{"default":"system"},"background":{"color":{"light":"#FDFDF7","dark":"#09090B"}},"navbar":{"links":[{"href":"https://platform.claude.com/","label":"Claude Developer Platform"}],"primary":{"type":"button","label":"Open Claude Code","href":"https://claude.ai/code"}},"footer":{"socials":{"x":"https://x.com/AnthropicAI","linkedin":"https://www.linkedin.com/company/anthropicresearch"},"links":[{"header":"Company","items":[{"label":"Anthropic","href":"https://www.anthropic.com/company"},{"label":"Careers","href":"https://www.anthropic.com/careers"},{"label":"Economic Futures","href":"https://www.anthropic.com/economic-futures"},{"label":"Research","href":"https://www.anthropic.com/research"},{"label":"News","href":"https://www.anthropic.com/news"},{"label":"Trust center","href":"https://trust.anthropic.com/"},{"label":"Transparency","href":"https://www.anthropic.com/transparency"}]},{"header":"Help and security","items":[{"label":"Availability","href":"https://www.anthropic.com/supported-countries"},{"label":"Status","href":"https://status.anthropic.com/"},{"label":"Support center","href":"https://support.claude.com/"}]},{"header":"Learn","items":[{"label":"Courses","href":"https://academy.claude.com/"},{"label":"MCP connectors","href":"https://claude.com/partners/mcp"},{"label":"Customer stories","href":"https://www.claude.com/customers"},{"label":"Engineering blog","href":"https://www.anthropic.com/engineering"},{"label":"Events","href":"https://www.anthropic.com/events"},{"label":"Powered by Claude","href":"https://claude.com/partners/powered-by-claude"},{"label":"Service partners","href":"https://claude.com/partners/services"},{"label":"Startups program","href":"https://claude.com/programs/startups"}]},{"header":"Terms and policies","items":[{"label":"Privacy choices","href":"https://www.anthropic.com/legal/privacy"},{"label":"Privacy policy","href":"https://www.anthropic.com/legal/privacy"},{"label":"Disclosure policy","href":"https://www.anthropic.com/responsible-disclosure-policy"},{"label":"Usage policy","href":"https://www.anthropic.com/legal/aup"},{"label":"Commercial terms","href":"https://www.anthropic.com/legal/commercial-terms"},{"label":"Consumer terms","href":"https://www.anthropic.com/legal/consumer-terms"}]}]},"seo":{"metatags":{"canonical":"https://code.claude.com/docs"}},"fonts":{"family":"Anthropic Sans"},"contextual":{"options":["copy","view","claude"],"display":"header"},"styling":{"latex":true},"navigation":{"languages":[{"language":"en","href":"en/overview"},{"language":"fr","href":"fr/overview"},{"language":"de","href":"de/overview"},{"language":"it","href":"it/overview"},{"language":"jp","href":"ja/overview"},{"language":"es","href":"es/overview"},{"language":"ko","href":"ko/overview"},{"language":"zh-CN","href":"zh-CN/overview"},{"language":"zh-TW","href":"zh-TW/overview"},{"language":"ru","href":"ru/overview"},{"language":"id","href":"id/overview"},{"language":"pt-BR","href":"pt/overview"}]}},"deployment":{"deploymentMetadataValue":{"subdomain":"claude-code","hasAudioNarration":false,"actualSubdomain":"claude-code","customDomains":["code.claude.com"],"gitSource":{"type":"github","owner":"anthropics","repo":"claude-code-docs","deployBranch":"main","contentDirectory":"","isPrivate":true,"mountPath":"","label":""},"chroma":{"liveDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85","collectionId":"5857522b-efb8-436a-af8d-9016a7b362b7","schemaVersion":"v3","latestBuiltDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85"},"feedback":{"thumbs":true},"entitlements":{"AI_CHAT":{"status":"ENABLED"},"REMOVE_BRANDING":{"status":"ENABLED"},"CONTEXTUAL_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"CODE_SNIPPET_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"WEB_MCP":{"status":"ENABLED"},"NARRATION":{"status":"ENABLED"}},"buildId":"6ae7a807e7a853c3110bf6c9","clientVersion":"0.0.4044","searchFilterCounts":[{"language":"en","tag":"Agent SDK","count":60},{"language":"en","tag":"Plugins","count":56},{"language":"de","tag":"Neuigkeiten","count":50},{"language":"en","tag":"What's New","count":50},{"language":"es","tag":"Novedades","count":50},{"language":"fr","tag":"Nouveautés","count":50},{"language":"it","tag":"Novità","count":50},{"language":"ko","tag":"새로운 기능","count":50},{"language":"pt-BR","tag":"Novidades","count":50},{"language":"ru","tag":"Что нового","count":50},{"language":"zh-TW","tag":"最新消息","count":50},{"language":"de","tag":"Erste Schritte","count":49},{"language":"es","tag":"Primeros pasos","count":49},{"language":"fr","tag":"Premiers pas","count":49},{"language":"id","tag":"Memulai","count":49},{"language":"it","tag":"Per iniziare","count":49},{"language":"jp","tag":"はじめに","count":49},{"language":"ko","tag":"시작하기","count":49},{"language":"pt-BR","tag":"Primeiros passos","count":49},{"language":"ru","tag":"Начало работы","count":49},{"language":"zh-TW","tag":"快速入門","count":49},{"language":"en","tag":"Getting started","count":48},{"language":"zh-CN","tag":"快速入门","count":46},{"language":"en","tag":"Overview","count":41},{"language":"de","tag":"Agent SDK","count":36},{"language":"en","tag":"Setup and access","count":36},{"language":"es","tag":"Agent SDK","count":36},{"language":"id","tag":"Agent SDK","count":36},{"language":"it","tag":"Agent SDK","count":36},{"language":"jp","tag":"Agent SDK","count":36},{"language":"pt-BR","tag":"Agent SDK","count":36},{"language":"ru","tag":"Agent SDK","count":36},{"language":"zh-CN","tag":"Agent SDK","count":36},{"language":"zh-TW","tag":"Agent SDK","count":36},{"language":"de","tag":"Administration","count":34},{"language":"en","tag":"Administration","count":34},{"language":"es","tag":"Administración","count":34},{"language":"fr","tag":"Administration","count":34},{"language":"id","tag":"Administrasi","count":34},{"language":"it","tag":"Amministrazione","count":34},{"language":"jp","tag":"管理","count":34},{"language":"ko","tag":"관리","count":34},{"language":"pt-BR","tag":"Administração","count":34},{"language":"ru","tag":"Администрирование","count":34},{"language":"zh-CN","tag":"管理","count":34},{"language":"zh-TW","tag":"管理","count":34},{"language":"de","tag":"Plugins","count":32},{"language":"es","tag":"Plugins","count":32},{"language":"fr","tag":"SDK Agent","count":32},{"language":"fr","tag":"Plugins","count":32},{"language":"id","tag":"Plugin","count":32},{"language":"it","tag":"Plugin","count":32},{"language":"jp","tag":"プラグイン","count":32},{"language":"ko","tag":"Agent SDK","count":32},{"language":"ko","tag":"플러그인","count":32},{"language":"pt-BR","tag":"Plugins","count":32},{"language":"ru","tag":"Плагины","count":32},{"language":"zh-CN","tag":"插件","count":32},{"language":"zh-TW","tag":"外掛","count":32},{"language":"en","tag":"Reference","count":28},{"language":"es","tag":"Configuración","count":28},{"language":"jp","tag":"設定","count":28},{"language":"zh-TW","tag":"設定","count":28},{"language":"de","tag":"Konfiguration","count":25},{"language":"en","tag":"Configuration","count":25},{"language":"fr","tag":"Configuration","count":25},{"language":"id","tag":"Konfigurasi","count":25},{"language":"id","tag":"Apa yang Baru","count":25},{"language":"id","tag":"Yang Baru","count":25},{"language":"it","tag":"Configurazione","count":25},{"language":"jp","tag":"新機能","count":25},{"language":"jp","tag":"最新情報","count":25},{"language":"ko","tag":"구성","count":25},{"language":"pt-BR","tag":"Configuração","count":25},{"language":"ru","tag":"Конфигурация","count":25},{"language":"zh-CN","tag":"配置","count":25},{"language":"zh-CN","tag":"新功能","count":25},{"language":"zh-CN","tag":"最新动态","count":25},{"language":"en","tag":"Settings","count":24},{"language":"de","tag":"Mit Claude Code entwickeln","count":22},{"language":"es","tag":"Crea con Claude Code","count":22},{"language":"fr","tag":"Développer avec Claude Code","count":22},{"language":"id","tag":"Membangun dengan Claude Code","count":22},{"language":"it","tag":"Crea con Claude Code","count":22},{"language":"jp","tag":"Claude Code で構築","count":22},{"language":"ko","tag":"Claude Code로 만들기","count":22},{"language":"pt-BR","tag":"Desenvolva com Claude Code","count":22},{"language":"ru","tag":"Разработка с Claude Code","count":22},{"language":"zh-CN","tag":"使用 Claude Code 构建","count":22},{"language":"zh-TW","tag":"使用 Claude Code 打造","count":22},{"language":"de","tag":"Referenz","count":20},{"language":"es","tag":"Referencia","count":20},{"language":"fr","tag":"Référence","count":20},{"language":"id","tag":"Referensi","count":20},{"language":"it","tag":"Riferimento","count":20},{"language":"jp","tag":"リファレンス","count":20},{"language":"ko","tag":"레퍼런스","count":20},{"language":"pt-BR","tag":"Referência","count":20},{"language":"ru","tag":"Справочник","count":20},{"language":"zh-CN","tag":"参考","count":20},{"language":"de","tag":"Plattformen und Integrationen","count":19},{"language":"es","tag":"Plataformas e integraciones","count":19},{"language":"fr","tag":"Plateformes et intégrations","count":19},{"language":"id","tag":"Platform dan integrasi","count":19},{"language":"it","tag":"Piattaforme e integrazioni","count":19},{"language":"jp","tag":"プラットフォームと連携","count":19},{"language":"ko","tag":"플랫폼 및 통합","count":19},{"language":"pt-BR","tag":"Plataformas e integrações","count":19},{"language":"ru","tag":"Платформы и интеграции","count":19},{"language":"zh-CN","tag":"平台与集成","count":19},{"language":"zh-TW","tag":"平台與整合","count":19},{"language":"de","tag":"Code-Review und Pull Requests","count":14},{"language":"es","tag":"Revisión de código y pull requests","count":14},{"language":"fr","tag":"Revue de code et pull requests","count":14},{"language":"it","tag":"Code review e pull request","count":14},{"language":"ko","tag":"코드 리뷰 및 풀 리퀘스트","count":14},{"language":"pt-BR","tag":"Revisão de código e pull requests","count":14},{"language":"ru","tag":"Код-ревью и pull request","count":14},{"language":"zh-TW","tag":"程式碼審查與 pull request","count":14},{"language":"zh-TW","tag":"部署","count":11}]},"assistantConfig":{"enableAskAiButton":false,"enableStarterQuestions":false,"enableAskAiSearchBar":true},"basePath":"/docs","hasChatPermissions":true,"hasWebMcpPermissions":true,"toggles":[{"name":"kill-isr","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"assistant-bash","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"chat-bucketing-batched","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"agent-mintlify-slack","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"agent-integrations-settings","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automations-pr-grouping","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"custom-prefix","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"analytics-v7","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"user-flows-analytics","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"no-publish-flow","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-onboarding","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"llms-txt-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"snapshot-serving-live","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"stripTemperatureMiddleware","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"support-platform-pylon-zendesk","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"snapshot-serving","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"instant-rollback","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"granular-notifications-server","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"granular-notifications","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automations-fable","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"fixed-ai-action-pricing","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automation-resolve-merge-conflict","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"scoped-publishing","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"mintql","enabled":true,"variant":{"name":"disabled","en

## Source (output-styles): https://docs.claude.com/en/docs/claude-code/output-styles

Output styles - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
An output style is a set of instructions that sets Claude’s role, tone, and response format for every response in a session. Claude Code includes four built-in styles besides its default, and you can write your own.
Use an output style to change the way Claude responds and works with you for a whole session, so you don’t repeat the request in each prompt. For example, a built-in style can make responses shorter, add an explanation of each change, or have Claude start work without asking routine questions. A custom style can also turn Claude into something other than a software engineer, such as a writing assistant or a data analyst.
To use a built-in style, pick one from the
built-in output styles
and
switch to it
.
To write your own instructions,
create a custom output style
.
An output style gives Claude instructions to follow. It doesn’t guarantee that something always happens or never happens. Some needs fit a different feature:
For what Claude should know about your project, use
CLAUDE.md
.
For something that has to happen every time, such as formatting after each edit or blocking a command, use a
hook
.
For skills, subagents, and the other options, see
Choose between an output style and other features
.
​
Built-in output styles
Claude Code starts in the
Default
style, its standard instructions for completing software engineering tasks. Each of the four other built-in styles keeps those instructions and adds its own.
This table shows what each style changes about a session and when it fits:
Style
What changes
Use it when
Proactive
Claude starts work right away and makes reasonable assumptions rather than asking about routine decisions
You want Claude to keep working through routine decisions, and you’ll correct course if an assumption is wrong
Concise
Responses lead with the result and leave out preamble, narration, and recaps
Default responses are longer than you want
Explanatory
Claude adds short
Insight
blocks that explain the choices behind the code it writes
You’re getting to know a codebase or want the reasoning along with the change
Learning
Claude explains its choices and leaves small pieces of code for you to write yourself
You want hands-on coding practice while the task still gets done
​
Default
Default means no output style is selected. Claude Code adds no style instructions, and Claude works from Claude Code’s standard system prompt, which is written for software engineering tasks.
default
appears in the
/output-style
list with the other styles, so you
select it the same way
.
​
Proactive
In the Proactive style, Claude starts implementing as soon as you send a task. It makes reasonable assumptions about routine decisions rather than stopping to ask, and it doesn’t switch to plan mode unless you ask for a plan. You can redirect it at any point.
The style’s instructions also tell Claude to check with you in the conversation before an action that deletes data or changes a shared or production system. That check is an instruction Claude follows and is separate from permission prompts.
Switching to the Proactive style doesn’t change your
permission mode
. Your permission mode still decides which tool calls run without asking you, so permission prompts appear the same way they did before you switched.
​
Concise
In the Concise style, the first sentence of a response states what happened or what the answer is. Claude leaves out the lead-in, the step-by-step narration, and the closing recap, and answers a simple question in one to three sentences. It does the engineering work as thoroughly as in the Default style. Requires Claude Code v2.1.237 or later.
Claude still writes at full length in these cases:
Anything you ask for
: when you ask for an explanation or more detail, Claude answers in full.
Anything you need in order to act safely
: error reports, failing test output, security warnings, and confirmations for destructive actions keep their complete content.
​
Explanatory
In the Explanatory style, Claude does the task the way it does in the Default style and adds short explanations of why it made the choices it made. Each explanation appears in the conversation, before or after the code it’s about, in a block labeled
Insight
. The explanations aren’t written into your files as comments.
An
Insight
block carries two or three points about your codebase or the code Claude wrote, such as this one after adding an API endpoint:
★ Insight ─────────────────────────────────────
- Every route in this repo goes through the withAuth wrapper, so the new endpoint gets session checks without its own middleware.
- Rate limits are set per route in limits.ts, which is why this change adds an entry there rather than a global default.
─────────────────────────────────────────────────
​
Learning
In the Learning style, Claude adds the same
Insight
blocks as the
Explanatory style
and also asks you to write some of the code. Claude handles routine implementation itself. When it reaches a piece with a real design decision, such as error handling, a data structure, or business logic with more than one valid approach, it leaves a few lines for you.
Claude marks the spot with a
TODO(human)
comment in the file, then sends a request that says what’s already built, what to write, and what to weigh:
● Learn by Doing
Context: The upload form is in place and calls validateFile() before accepting a file. Size and type checks work for images, but the switch statement has no handling for documents yet.
Your Task: In upload.js, implement the case "document" branch inside validateFile(). Look for TODO(human).
Guidance: Decide on a size limit for documents and whether the file extension has to match the MIME type. Return {valid: boolean, error?: string}.
Claude then stops and waits. Write your code at the
TODO(human)
comment and tell Claude when you’re done. Claude responds with one
Insight
about your code and continues the task.
​
Change your output style
Pick a style with the command, a menu, or a settings file. The command and both menus save your choice to
.claude/settings.local.json
at the
local project level
.
/output-style
command
: run
/output-style <style>
to switch, for example
/output-style concise
. With no argument, the command lists the styles you can pick and marks the current one.
The command also works in
non-interactive mode
and Agent SDK sessions, and from the mobile app or web via
Remote Control
, where you can list and select only
built-in styles
. Requires Claude Code v2.1.269 or later.
Terminal menu
: run
/config
and select
Output style
to pick a style from a menu.
VS Code extension
: open the
command menu
with
/
and select
Output styles
to pick a style, including your custom styles. Requires Claude Code v2.1.257 or later.
Desktop app
: set the
outputStyle
field in a settings file, for example
.claude/settings.local.json
, the file the terminal menu writes. When you run
/config
there, Claude Code
opens
Settings > Code
or
Settings > Claude Code
rather than a menu.
To set a style without the menu, edit the
outputStyle
field directly in a settings file:
{
"outputStyle"
:
"Explanatory"
}
The value is case-sensitive, so write the built-in names as
Proactive
,
Concise
,
Explanatory
, and
Learning
. A value that doesn’t match a style name exactly, such as
explanatory
, gives you the Default style. The
/output-style
command ignores case.
To make a style your default across projects, set
outputStyle
in
~/.claude/settings.json
. A project’s own settings files
take precedence
over that value.
When you switch styles mid-session, Claude uses the new style starting with your next message. For what that first message costs in prompt caching, see
Changing output style
. Before v2.1.251, the new style applied only after you ran
/clear
or started a new session.
​
Create a custom output style
A custom output style is a Markdown file: frontmatter for metadata, then the instructions for Claude.
In the VS Code extension, you can also create the file from the
Output styles
menu
rather than writing it by hand. This requires Claude Code v2.1.261 or later.
1
Create a Markdown file
Save it at one of three levels. The file name becomes the style name unless you set
name
in the frontmatter.
User:
~/.claude/output-styles
Project:
.claude/output-styles
Managed policy:
.claude/output-styles
inside the
managed settings directory
Project output styles load from every
.claude/output-styles/
between the working directory and the repository root. When more than one of these nested directories defines a style with the same name, Claude Code uses the one closest to the working directory.
2
Add frontmatter and instructions
Decide whether to keep Claude Code’s software engineering instructions. Set
keep-coding-instructions: true
if you’re changing how Claude communicates but still want it coding the same way. Leave it out if Claude won’t be doing software engineering.
This example leads every explanation with a diagram while keeping Claude’s coding behavior:
---
name
:
Diagrams first
description
:
Lead every explanation with a diagram
keep-coding-instructions
:
true
---
When explaining code, architecture, or data flow, start with a Mermaid diagram showing the structure, then explain in prose.
## Diagram conventions
Use
`flowchart TD`
for control flow and
`sequenceDiagram`
for request paths. Keep diagrams under 15 nodes.
3
Switch to your style
Run
/output-style <style>
in the terminal, or run
/config
and select your style under
Output style
. Claude uses the new style starting with your next message. In the terminal, Claude Code reads style files when it starts, so if you create or edit one during a running session, restart Claude Code to pick up the change.
Plugins
can also ship output styles in an
output-styles/
directory.
​
Frontmatter reference
Configure an output style with YAML
frontmatter
between
---
markers at the top of the file. All fields are optional, and field names use lowercase words separated by hyphens. A misspelled field is ignored without an error. If the YAML doesn’t parse, the style still loads under its file name with no fields set; run
claude --debug
to see the parse error.
Field
Required
Description
name
No
Name of the output style, shown in the
/config
picker. Default: the file name
description
No
Description of the output style, shown in the
/config
picker
keep-coding-instructions
No
Set to
true
to keep Claude Code’s section of built-in software engineering instructions, which only the full system prompt includes, alongside your style. See
How output styles work
. Default:
false
force-for-plugin
No
Plugin output styles only. Set to
true
to apply this style automatically whenever the plugin is enabled, without requiring users to select it. Overrides the user’s
outputStyle
setting. If multiple enabled plugins set this, Claude Code uses the first one loaded. Default:
false
​
Choose between an output style and other features
An output style applies to every response in a session. It’s an instruction Claude follows, so nothing enforces it. When what you want is narrower than every response, or has to happen without fail, another feature fits better.
This table matches what you want to the feature that does it:
You want
Use
Why it fits
Every response in a certain voice, length, or format, or Claude in a different role
An output style
It applies to the whole session, and you switch styles with one command
Claude to know your project’s conventions, commands, and structure
CLAUDE.md
It holds what Claude should know about the codebase, and it stays loaded whichever style you pick
Instructions for one kind of task, such as a release checklist or a review procedure
A
skill
Claude loads it only when you invoke it or the task matches, so it doesn’t shape unrelated responses
Something to happen every time without exception, such as formatting after each edit or blocking a command
A
hook
Claude Code runs a hook itself at a lifecycle event, so it doesn’t depend on Claude following an instruction
A helper with its own instructions, model, and tools for a focused task
A
subagent
It runs in a separate context with its own system prompt and returns a summary to your conversation
An addition to Claude’s instructions that you pass when you start Claude Code
--append-system-prompt
It appends to the system prompt without removing anything
These features combine. For example, you can use CLAUDE.md for what Claude should know, an output style for how it responds, and a hook for anything that has to be guaranteed.
Extend Claude Code
compares the rest of the extension features.
​
How output styles work
An output style changes the instructions Claude Code gives Claude.
Claude Code sends the active style’s instructions with every request.
On the full system prompt, custom output styles leave out Claude Code’s section of built-in software engineering instructions, such as how to scope changes, write comments, and verify work, unless
keep-coding-instructions
is set to
true
. The shorter system prompt doesn’t include that section, so the field has no effect there. To rely on the field, set
CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT
to
0
, which selects the full prompt on any model.
Output styles apply to the main conversation and to a
fork
, which inherits the parent’s whole conversation and system prompt. Other
subagents run their own system prompt
, so styles don’t change how they respond.
Token usage depends on the style. A style’s instructions add input tokens, though prompt caching reduces this cost after the first request in a session.
The built-in Explanatory and Learning styles produce longer responses than Default by design, which increases output tokens. The Concise style does the opposite by instructing Claude to keep responses short by default. For custom styles, output token usage depends on what your instructions tell Claude to produce.
​
Related resources
Settings
: where the
outputStyle
field lives and how settings precedence works
Permission modes
: how the Proactive style compares to auto mode
Plugins
: package and distribute output styles alongside skills, hooks, and agents
Debug your configuration
: diagnose why an output style isn’t taking effect
Was this page helpful?
Yes
No
{"docsConfig":{"theme":"mint","$schema":"https://mintlify.com/docs.json","name":"Claude Code Docs","description":"Official documentation for Claude Code, Anthropic's agentic coding tool available in the terminal, IDE, desktop app, and browser. Covers installation, configuration, skills, subagents, hooks, MCP, the Agent SDK, and reference material.","colors":{"primary":"#0E0E0E","light":"#D4A27F","dark":"#0E0E0E"},"logo":{"light":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/light.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=78fd01ff4f4340295a4f66e2ea54903c","dark":"https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/logo/dark.svg?fit=max\u0026auto=format\u0026n=c5r9_6tjPMzFdDDT\u0026q=85\u0026s=1298a0c3b3a1da603b190d0de0e31712"},"favicon":"https://mintcdn.com/claude-code/T2WlxklWBkR5Y1mJ/favicon.ico?fit=max\u0026auto=format\u0026n=T2WlxklWBkR5Y1mJ\u0026q=85\u0026s=346a85952ae08d5ee90e3c34d4423930","appearance":{"default":"system"},"background":{"color":{"light":"#FDFDF7","dark":"#09090B"}},"navbar":{"links":[{"href":"https://platform.claude.com/","label":"Claude Developer Platform"}],"primary":{"type":"button","label":"Open Claude Code","href":"https://claude.ai/code"}},"footer":{"socials":{"x":"https://x.com/AnthropicAI","linkedin":"https://www.linkedin.com/company/anthropicresearch"},"links":[{"header":"Company","items":[{"label":"Anthropic","href":"https://www.anthropic.com/company"},{"label":"Careers","href":"https://www.anthropic.com/careers"},{"label":"Economic Futures","href":"https://www.anthropic.com/economic-futures"},{"label":"Research","href":"https://www.anthropic.com/research"},{"label":"News","href":"https://www.anthropic.com/news"},{"label":"Trust center","href":"https://trust.anthropic.com/"},{"label":"Transparency","href":"https://www.anthropic.com/transparency"}]},{"header":"Help and security","items":[{"label":"Availability","href":"https://www.anthropic.com/supported-countries"},{"label":"Status","href":"https://status.anthropic.com/"},{"label":"Support center","href":"https://support.claude.com/"}]},{"header":"Learn","items":[{"label":"Courses","href":"https://academy.claude.com/"},{"label":"MCP connectors","href":"https://claude.com/partners/mcp"},{"label":"Customer stories","href":"https://www.claude.com/customers"},{"label":"Engineering blog","href":"https://www.anthropic.com/engineering"},{"label":"Events","href":"https://www.anthropic.com/events"},{"label":"Powered by Claude","href":"https://claude.com/partners/powered-by-claude"},{"label":"Service partners","href":"https://claude.com/partners/services"},{"label":"Startups program","href":"https://claude.com/programs/startups"}]},{"header":"Terms and policies","items":[{"label":"Privacy choices","href":"https://www.anthropic.com/legal/privacy"},{"label":"Privacy policy","href":"https://www.anthropic.com/legal/privacy"},{"label":"Disclosure policy","href":"https://www.anthropic.com/responsible-disclosure-policy"},{"label":"Usage policy","href":"https://www.anthropic.com/legal/aup"},{"label":"Commercial terms","href":"https://www.anthropic.com/legal/commercial-terms"},{"label":"Consumer terms","href":"https://www.anthropic.com/legal/consumer-terms"}]}]},"seo":{"metatags":{"canonical":"https://code.claude.com/docs"}},"fonts":{"family":"Anthropic Sans"},"contextual":{"options":["copy","view","claude"],"display":"header"},"styling":{"latex":true},"navigation":{"languages":[{"language":"en","href":"en/overview"},{"language":"fr","href":"fr/overview"},{"language":"de","href":"de/overview"},{"language":"it","href":"it/overview"},{"language":"jp","href":"ja/overview"},{"language":"es","href":"es/overview"},{"language":"ko","href":"ko/overview"},{"language":"zh-CN","href":"zh-CN/overview"},{"language":"zh-TW","href":"zh-TW/overview"},{"language":"ru","href":"ru/overview"},{"language":"id","href":"id/overview"},{"language":"pt-BR","href":"pt/overview"}]}},"deployment":{"deploymentMetadataValue":{"subdomain":"claude-code","hasAudioNarration":false,"actualSubdomain":"claude-code","customDomains":["code.claude.com"],"gitSource":{"type":"github","owner":"anthropics","repo":"claude-code-docs","deployBranch":"main","contentDirectory":"","isPrivate":true,"mountPath":"","label":""},"chroma":{"liveDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85","collectionId":"5857522b-efb8-436a-af8d-9016a7b362b7","schemaVersion":"v3","latestBuiltDeploymentHistoryId":"6ae7a28bd14d2161b5f1ff85"},"feedback":{"thumbs":true},"entitlements":{"AI_CHAT":{"status":"ENABLED"},"REMOVE_BRANDING":{"status":"ENABLED"},"CONTEXTUAL_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"CODE_SNIPPET_FEEDBACK":{"status":"ENABLED","enabled":"ENABLED"},"WEB_MCP":{"status":"ENABLED"},"NARRATION":{"status":"ENABLED"}},"buildId":"6ae7a807e7a853c3110bf6c9","clientVersion":"0.0.4044","searchFilterCounts":[{"language":"en","tag":"Agent SDK","count":60},{"language":"en","tag":"Plugins","count":56},{"language":"de","tag":"Neuigkeiten","count":50},{"language":"en","tag":"What's New","count":50},{"language":"es","tag":"Novedades","count":50},{"language":"fr","tag":"Nouveautés","count":50},{"language":"it","tag":"Novità","count":50},{"language":"ko","tag":"새로운 기능","count":50},{"language":"pt-BR","tag":"Novidades","count":50},{"language":"ru","tag":"Что нового","count":50},{"language":"zh-TW","tag":"最新消息","count":50},{"language":"de","tag":"Erste Schritte","count":49},{"language":"es","tag":"Primeros pasos","count":49},{"language":"fr","tag":"Premiers pas","count":49},{"language":"id","tag":"Memulai","count":49},{"language":"it","tag":"Per iniziare","count":49},{"language":"jp","tag":"はじめに","count":49},{"language":"ko","tag":"시작하기","count":49},{"language":"pt-BR","tag":"Primeiros passos","count":49},{"language":"ru","tag":"Начало работы","count":49},{"language":"zh-TW","tag":"快速入門","count":49},{"language":"en","tag":"Getting started","count":48},{"language":"zh-CN","tag":"快速入门","count":46},{"language":"en","tag":"Overview","count":41},{"language":"de","tag":"Agent SDK","count":36},{"language":"en","tag":"Setup and access","count":36},{"language":"es","tag":"Agent SDK","count":36},{"language":"id","tag":"Agent SDK","count":36},{"language":"it","tag":"Agent SDK","count":36},{"language":"jp","tag":"Agent SDK","count":36},{"language":"pt-BR","tag":"Agent SDK","count":36},{"language":"ru","tag":"Agent SDK","count":36},{"language":"zh-CN","tag":"Agent SDK","count":36},{"language":"zh-TW","tag":"Agent SDK","count":36},{"language":"de","tag":"Administration","count":34},{"language":"en","tag":"Administration","count":34},{"language":"es","tag":"Administración","count":34},{"language":"fr","tag":"Administration","count":34},{"language":"id","tag":"Administrasi","count":34},{"language":"it","tag":"Amministrazione","count":34},{"language":"jp","tag":"管理","count":34},{"language":"ko","tag":"관리","count":34},{"language":"pt-BR","tag":"Administração","count":34},{"language":"ru","tag":"Администрирование","count":34},{"language":"zh-CN","tag":"管理","count":34},{"language":"zh-TW","tag":"管理","count":34},{"language":"de","tag":"Plugins","count":32},{"language":"es","tag":"Plugins","count":32},{"language":"fr","tag":"SDK Agent","count":32},{"language":"fr","tag":"Plugins","count":32},{"language":"id","tag":"Plugin","count":32},{"language":"it","tag":"Plugin","count":32},{"language":"jp","tag":"プラグイン","count":32},{"language":"ko","tag":"Agent SDK","count":32},{"language":"ko","tag":"플러그인","count":32},{"language":"pt-BR","tag":"Plugins","count":32},{"language":"ru","tag":"Плагины","count":32},{"language":"zh-CN","tag":"插件","count":32},{"language":"zh-TW","tag":"外掛","count":32},{"language":"en","tag":"Reference","count":28},{"language":"es","tag":"Configuración","count":28},{"language":"jp","tag":"設定","count":28},{"language":"zh-TW","tag":"設定","count":28},{"language":"de","tag":"Konfiguration","count":25},{"language":"en","tag":"Configuration","count":25},{"language":"fr","tag":"Configuration","count":25},{"language":"id","tag":"Konfigurasi","count":25},{"language":"id","tag":"Apa yang Baru","count":25},{"language":"id","tag":"Yang Baru","count":25},{"language":"it","tag":"Configurazione","count":25},{"language":"jp","tag":"新機能","count":25},{"language":"jp","tag":"最新情報","count":25},{"language":"ko","tag":"구성","count":25},{"language":"pt-BR","tag":"Configuração","count":25},{"language":"ru","tag":"Конфигурация","count":25},{"language":"zh-CN","tag":"配置","count":25},{"language":"zh-CN","tag":"新功能","count":25},{"language":"zh-CN","tag":"最新动态","count":25},{"language":"en","tag":"Settings","count":24},{"language":"de","tag":"Mit Claude Code entwickeln","count":22},{"language":"es","tag":"Crea con Claude Code","count":22},{"language":"fr","tag":"Développer avec Claude Code","count":22},{"language":"id","tag":"Membangun dengan Claude Code","count":22},{"language":"it","tag":"Crea con Claude Code","count":22},{"language":"jp","tag":"Claude Code で構築","count":22},{"language":"ko","tag":"Claude Code로 만들기","count":22},{"language":"pt-BR","tag":"Desenvolva com Claude Code","count":22},{"language":"ru","tag":"Разработка с Claude Code","count":22},{"language":"zh-CN","tag":"使用 Claude Code 构建","count":22},{"language":"zh-TW","tag":"使用 Claude Code 打造","count":22},{"language":"de","tag":"Referenz","count":20},{"language":"es","tag":"Referencia","count":20},{"language":"fr","tag":"Référence","count":20},{"language":"id","tag":"Referensi","count":20},{"language":"it","tag":"Riferimento","count":20},{"language":"jp","tag":"リファレンス","count":20},{"language":"ko","tag":"레퍼런스","count":20},{"language":"pt-BR","tag":"Referência","count":20},{"language":"ru","tag":"Справочник","count":20},{"language":"zh-CN","tag":"参考","count":20},{"language":"de","tag":"Plattformen und Integrationen","count":19},{"language":"es","tag":"Plataformas e integraciones","count":19},{"language":"fr","tag":"Plateformes et intégrations","count":19},{"language":"id","tag":"Platform dan integrasi","count":19},{"language":"it","tag":"Piattaforme e integrazioni","count":19},{"language":"jp","tag":"プラットフォームと連携","count":19},{"language":"ko","tag":"플랫폼 및 통합","count":19},{"language":"pt-BR","tag":"Plataformas e integrações","count":19},{"language":"ru","tag":"Платформы и интеграции","count":19},{"language":"zh-CN","tag":"平台与集成","count":19},{"language":"zh-TW","tag":"平台與整合","count":19},{"language":"de","tag":"Code-Review und Pull Requests","count":14},{"language":"es","tag":"Revisión de código y pull requests","count":14},{"language":"fr","tag":"Revue de code et pull requests","count":14},{"language":"it","tag":"Code review e pull request","count":14},{"language":"ko","tag":"코드 리뷰 및 풀 리퀘스트","count":14},{"language":"pt-BR","tag":"Revisão de código e pull requests","count":14},{"language":"ru","tag":"Код-ревью и pull request","count":14},{"language":"zh-TW","tag":"程式碼審查與 pull request","count":14},{"language":"zh-TW","tag":"部署","count":11}]},"assistantConfig":{"enableAskAiButton":false,"enableStarterQuestions":false,"enableAskAiSearchBar":true},"basePath":"/docs","hasChatPermissions":true,"hasWebMcpPermissions":true,"toggles":[{"name":"kill-isr","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"assistant-bash","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"chat-bucketing-batched","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"agent-mintlify-slack","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"agent-integrations-settings","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automations-pr-grouping","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"custom-prefix","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"analytics-v7","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"user-flows-analytics","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"no-publish-flow","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-onboarding","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"llms-txt-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"snapshot-serving-live","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"stripTemperatureMiddleware","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"support-platform-pylon-zendesk","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"snapshot-serving","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"instant-rollback","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"granular-notifications-server","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"granular-notifications","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automations-fable","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"fixed-ai-action-pricing","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"automation-resolve-merge-conflict","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"scoped-publishing","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"mintql","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"page-level-analytics","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"editor-version-history-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"billing-page-v2","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"full-page-search","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workspace-projects","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"assistant-v5","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"byok-sep-25","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"fork-pr-previews","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"revalidation-jwt","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"vite-origin","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"billing-updated-9-15","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-sso-scim","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"hobby-abuse-scan","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"dashboard-inbox","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-signup","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"turbopuffer-dual-write","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"workos-enabled","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"approve-review-flow","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false},{"name":"sso-setup-deadline-banner","enabled":true,"variant":{"name":"disabled","enabled":false,"feature_enabled":true},"impressionData":false}],"googleFontsInlined":false},"customCss":[{"filePath":"button.css","content":".btn{position:relative;display:inline-flex;gap:.5rem;align-items:center;justify-content:center;flex-shrink:0;min-width:5rem;height:2.25rem;padding:.5rem 1rem;white-space:nowrap;font-family:Styrene;font-weight:600;border-radius:.5rem}"},{"filePath":"style.css","content":"@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-Regular-Static.otf) format(\"opentype\");font-weight:400;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-RegularItalic-Static.otf) format(\"opentype\");font-weight:400;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-Medium-Static.otf) format(\"opentype\");font-weight:500;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-MediumItalic-Static.otf) format(\"opentype\");font-weight:500;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-Semibold-Static.otf) format(\"opentype\");font-weight:600;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-SemiboldItalic-Static.otf) format(\"opentype\");font-weight:600;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-Bold-Static.otf) format(\"opentype\");font-weight:700;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Sans\";src:url(https://assets.claude.ai/Fonts/AnthropicSans-Text-BoldItalic-Static.otf) format(\"opentype\");font-weight:700;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Serif Display\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Display-Regular-Static.otf) format(\"opentype\");font-weight:400;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif Display\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Display-RegularItalic-Static.otf) format(\"opentype\");font-weight:400;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Serif Display\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Display-Medium-Static.otf) format(\"opentype\");font-weight:500;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif Display\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Display-Semibold-Static.otf) format(\"opentype\");font-weight:600;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif Display\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Display-Bold-Static.otf) format(\"opentype\");font-weight:700;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-Regular-Static.otf) format(\"opentype\");font-weight:400;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-RegularItalic-Static.otf) format(\"opentype\");font-weight:400;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-Medium-Static.otf) format(\"opentype\");font-weight:500;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-MediumItalic-Static.otf) format(\"opentype\");font-weight:500;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-Semibold-Static.otf) format(\"opentype\");font-weight:600;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-SemiboldItalic-Static.otf) format(\"opentype\");font-weight:600;font-style:italic;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-Bold-Static.otf) format(\"opentype\");font-weight:700;font-style:normal;font-display:swap}@font-face{font-family:\"Anthropic Serif\";src:url(https://assets.claude.ai/Fonts/AnthropicSerif-Text-BoldItalic-Static.otf) format(\"opentype\");font-weight:700;font-style:italic;font-display:swap}:root{--always-white:0 0% 100%;--always-black:0 0% 0%;--constant-book-cloth:15 55% 80%;--constant-clay:15 60% 85%;--constant-kraft:25 40% 83%;--constant-manilla:40 20% 92%;--constant-slate-000:0 0% 100%;--constant-slate-050:48 33.3% 97.1%;--constant-slate-100:53 28.6% 94.5%;--constant-slate-150:48 25% 92.2%;--constant-slate-200:50 20.7% 88.6%;--constant-slate-250:51 16.5% 84.5%;--constant-slate-300:50 11.5% 79.6%;--constant-slate-350:50 9% 73.7%;--constant-slate-400:49 6.5% 66.9%;--constant-slate-450:48 4.8% 59.2%;--constant-slate-500:53 3.2% 51.4%;--constant-slate-550:51 3.1% 43.7%;--constant-slate-600:48 2.7% 35.9%;--constant-slate-650:48 3.4% 29.2%;--constant-slate-700:60 2.5% 23.3%;--constant-slate-750:60 2.1% 18.4%;--constant-slate-800:60 2.7% 14.5%;--constant-slate-850:30 3.3% 11.8%;--constant-slate-900:30 4% 9.8%;--constant-slate-950:60 2.6% 7.6%;--constant-slate-1000:60 3.4% 5.7%}:root:not(.dark){--accent-brand:15 63.1% 59.6%;--accent-main-000:15 55.6% 52.4%;--accent-main-100:15 55.6% 52.4%;--accent-main-200:15 63.1% 59.6%;--accent-main-900:0 0% 0%;--accent-pro-000:251 34.2% 33.3%;--accent-pro-100:251 40% 45.1%;--accent-pro-200:251 61% 72.2%;--accent-pro-900:253 33.3% 91.8%;--accent-secondary-000:210 73.7% 40.2%;--accent-secondary-100:210 70.9% 51.6%;--accent-secondary-200:210 70.9% 51.6%;--accent-secondary-900:211 72% 90%;--bg-000:0 0% 100%;--bg-100:48 33.3% 97.1%;--bg-200:53 28.6% 94.5%;--bg-300:48 25% 92.2%;--bg-400:50 20.7% 88.6%;--bg-500:50 20.7% 88.6%;--border-100:30 3.3% 11.8%;--border-200:30 3.3% 11.8%;--border-300:30 3.3% 11.8%;--border-400:30 3.3% 11.8%;--danger-000:0 61.4% 22.4%;--danger-100:0 58.6% 34.1%;--danger-200:0 58.6% 34.1%;--danger-900:0 50% 95%;--oncolor-100:0 0% 100%;--oncolor-200:60 6.7% 97.1%;--oncolor-300:60 6.7% 97.1%;--text-000:60 2.6% 7.6%;--text-100:60 2.6% 7.6%;--text-200:60 2.5% 23.3%;--text-300:60 2.5% 23.3%;--text-400:51 3.1% 43.7%;--text-500:51 3.1% 43.7%}:root.dark{--accent-brand:15 63.1% 59.6%;--accent-main-000:15 55.6% 52.4%;--accent-main-100:15 63.1% 59.6%;--accent-main-200:15 63.1% 59.6%;--accent-main-900:0 0% 0%;--accent-pro-000:251 84.6% 74.5%;--accent-pro-100:251 40.2% 54.1%;--accent-pro-200:251 40% 45.1%;--accent-pro-900:250 25.3% 19.4%;--accent-secondary-000:210 71.1% 62%;--accent-secondary-100:210 70.9% 51.6%;--accent-secondary-200:210 70.9% 51.6%;--accent-secondary-900:210 55.9% 24.6%;--bg-000:60 2.1% 18.4%;--bg-100:60 2.7% 14.5%;--bg-200:30 3.3% 11.8%;--bg-300:60 2.6% 7.6%;--bg-400:60 3.4% 5.7%;--bg-500:60 3.4% 5.7%;--border-100:51 16.5% 84.5%;--border-200:51 16.5% 84.5%;--border-300:51 16.5% 84.5%;--border-400:51 16.5% 84.5%;--danger-000:0 73.1% 66.5%;--danger-100:0 58.6% 34.1%;--danger-200:0 58.6% 34.1%;--danger-900:0 23% 15.6%;--oncolor-100:0 0% 100%;--oncolor-200:60 6.7% 97.1%;--oncolor-300:60 6.7% 97.1%;--text-000:48 33.3% 97.1%;--text-100:48 33.3% 97.1%;--text-200:50 9% 73.7%;--text-300:50 9% 73.7%;--text-400:48 4.8% 59.2%;--text-500:48 4.8% 59.2%}#home-header{font-family:\"Anthropic Sans\",system-ui,\"Segoe UI\",Roboto,Helvetica,Arial,sans-serif;font-weight:400!important;font-size:50px;line-height:1.2;margin-bottom:1rem;color:--text-000;display:flex;align-items:baseline;justify-content:center;flex-wrap:nowrap}#localization-select-trigger>:has(img[src*=flags]),div[id^=localization-select-item]>:has(img[src*=flags]){display:none}@media (min-width:768px){#home-header{justify-content:center}}.build-with{font-family:\"Anthropic Sans\",system-ui,\"Segoe UI\",Roboto,Helvetica,Arial,sans-serif;letter-spacing:-.02em}.claude-wordmark-wrapper{display:inline-flex;align-items:baseline;margin-left:10px}.claude-wordmark{height:40px;width:auto;position:relative}.dark #home-header,.dark .description-text{color:#fff}.description-text{color:#000}.dark .claude-wordmark{filter:invert(1)}:root{--bg-color:#f0efea}.dark{--bg-color:#2b2b2b}#category-select,#content-container,#table-of-contents,.dropdown-item,.eyebrow,body,input{font-family:\"Anthropic Sans\",system-ui,\"Segoe UI\",Roboto,Helvetica,Arial,sans-serif}.eyebrow{text-transform:uppercase;letter-spacing:.02rem}#content-container h1,#content-container h2,#content-container h3,#content-container h4,#content-container h5,#content-container h6{font-family:\"Anthropic Serif Display\",Georgia,\"Times New Roman\",Times,serif;font-weight:400;letter-spacing:0;word-spacing:.1em}#content-container p{font-size:1rem;line-height:1.65rem}.font-extrabold{font-weight:600!important}.wide-table{width:100%;overflow-x:auto}.wide-table table{width:175%;margin-bottom:0}#prompt-library-container{margin:4rem auto;max-width:48rem;padding-left:1.25rem;padding-right:1.25rem}.prompt-library-title{font-size:24px;text-align:center;font-weight:700;color:#1f2937}.dark .prompt-library-title{color:#e5e7eb}.prompt-library-description{margin-top:1rem;text-align:center}.main-content{margin-bottom:10rem;max-width:64rem;margin-left:auto;margin-right:auto;padding-left:1.25rem;padding-right:1.25rem}.prompt-controllers{display:flex;gap:.5rem}.prompt-search-container{position:relative;flex:1 1 0%}.prompt-search-icon-container{display:flex;position:absolute;top:0;bottom:0;left:0;align-items:center;padding-left:.75rem}.prompt-search-icon{margin-left:.25rem;margin-right:.75rem;flex:none;width:1rem;height:1rem;background-color:#6b7280;mask-image:url(https://mintlify.b-cdn.net/v6.5.1/solid/magnifying-glass.svg);mask-repeat:no-repeat;mask-position:center center}input.prompt-search-bar{display:block;height:2.5rem;padding-left:2.5rem;border-radius:.75rem;border-width:1px;background-color:#fff;width:100%;color:#111827;box-shadow:0 1px 2px 0 rgba(0,0,0,.05)}.dark input.prompt-search-bar{color:#fff;background-color:rgb(var(--background-dark));border-color:#d1d5db1a}input.prompt-search-bar:focus{outline-color:rgb(var(--primary))}.dark input.prompt-search-bar:focus{outline-color:rgb(var(--primary-light))}.dark .dropdown-icon,.dark .prompt-search-icon{background-color:#ffffff80}#category-select{padding-left:1rem;padding-right:2.5rem;height:2.5rem;display:flex;align-items:center;border-radius:.75rem;border-width:1px;color:#111827;background-color:#fff;cursor:pointer;box-shadow:0 1px 2px 0 rgba(0,0,0,.05);white-space:nowrap}.dark #category-select{background-color:rgb(var(--background-dark));border-color:#d1d5db1a;color:#fff}#category-select:hover,.dropdown-item:hover{background-color:#f9fafb}.dark #category-select:hover,.dark .dropdown-item:hover{background-color:#ffffff0d}#category-select:focus{outline-color:rgb(var(--primary))}.dark #category-select:focus{outline-color:rgb(var(--primary-light))}#categories-dropdown{top:calc(100% + 4px);padding:.5rem;display:none;position:absolute;z-index:10;border-radius:.75rem;border-width:1px;width:100%;color:#111827;background-color:#fff;box-shadow:0 1px 2px 0 rgba(0,0,0,.05)}.dark #categories-dropdown{background-color:rgb(var(--background-dark));border-color:#d1d5db1a;color:#fff}#categories-dropdown-clickout{position:fixed;top:0;right:0;bottom:0;left:0;z-index:0}.dropdown-icon-container{display:flex;position:absolute;top:0;bottom:0;right:0;align-items:center;padding-right:.25rem}.dropdown-icon{margin-left:.25rem;margin-right:.75rem;flex:none;width:.75rem;height:.75rem;background-color:#6b7280;mask-image:url(https://mintlify.b-cdn.net/v6.5.1/solid/caret-down.svg);mask-repeat:no-repeat;mask-position:center center}#prompts-container{grid-template-columns:repeat(1,minmax(0,1fr));gap:2rem;display:grid;margin-top:2.5rem}.dropdown-item{padding:.25rem .5rem;border-radius:.375rem;display:flex;align-items:center;cursor:pointer}.check-icon{mask-image:url(https://mintlify.b-cdn.net/v6.5.1/solid/check.svg);height:.875rem;width:1rem;background-color:rgb(var(--primary-light));mask-repeat:no-repeat;mask-position:center center}.prompt-card{margin:-.75rem;padding:.75rem;display:flex;border-radius:1rem}.prompt-card:hover{background-color:#03071208}.dark .prompt-card:hover{background-color:#ffffff08}.prompt-icon-container{display:flex;flex:none;align-items:center;justify-content:center;margin-right:1.5rem;border-radius:.75rem;height:4rem;width:4rem;background-color:#cb785c1a}.prompt-icon{height:1.5rem;width:1.5rem;background-color:rgb(var(--primary-light));mask-repeat:no-repeat;mask-position:center center}.prompt-title{color:rgb(31 41 55);font-weight:600}.dark .prompt-title{color:rgb(229 231 235)}.prompt-description{margin-top:.25rem}@media (min-width:640px){#category-select{width:16rem}}@media (min-width:1024px){#prompts-container{grid-template-columns:repeat(2,minmax(0,1fr))}}.home-cards-custom{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(2,auto);gap:1.5rem}.home-cards-custom .card{background:0 0;border:.5px solid hsl(var(--border-300));border-radius:12px;padding:.25rem}@media (max-width:1024px){.home-cards-custom{grid-template-columns:repeat(2,1fr);grid-template-rows:repeat(3,auto)}}@media (max-width:768px){.home-cards-custom{grid-template-columns:1fr;grid-template-rows:repeat(6,auto)}}.relative{position:relative}.flex-1{flex:1 1 0%}.mermaid{position:relative;background-color:#fdfdfb;background-image:linear-gradient(rgba(235,219,188,.25) 1px,transparent 1px),linear-gradient(90deg,rgba(235,219,188,.25) 1px,transparent 1px),linear-gradient(rgba(235,219,188,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(235,219,188,.1) 1px,transparent 1px);background-size:20px 20px,20px 20px,4px 4px,4px 4px;background-position:-1px -1px,-1px -1px,-1px -1px,-1px -1px;padding:20px;border-radius:8px;border:1px solid rgba(235,219,188,.4);box-shadow:0 2px 4px rgba(64,64,62,.08)}.dark .mermaid{background-color:#1a1918;background-image:linear-gradient(rgba(212,162,127,.15) 1px,transparent 1px),linear-gradient(90deg,rgba(212,162,127,.15) 1px,transparent 1px),linear-gradient(rgba(212,162,127,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(212,162,127,.08) 1px,transparent 1px);border:1px solid rgba(102,102,99,.5);box-shadow:0 2px 4px rgba(0,0,0,.2)}.digest-meta{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem 1rem;padding:.75rem 1rem;margin:1.5rem 0 2.5rem;border:1px solid hsl(var(--border-300)/.15);background:hsl(var(--bg-200));font-variant-numeric:tabular-nums;font-size:.875rem;color:hsl(var(--text-400))}#content-container .digest-meta a{color:hsl(var(--accent-main-100));font-weight:500;text-decoration:none;border-bottom:none}#content-container .digest-meta a:hover{text-decoration:underline}.digest-feature{position:relative;margin:2.5rem 0;padding:1.875rem 1.875rem 1.625rem;background:radial-gradient(circle,hsl(var(--text-000)/.025) 1px,transparent 1px) 0 0/18px 18px,linear-gradient(180deg,hsl(var(--constant-manilla)/.55),hsl(var(--constant-manilla)/.38));border:1px solid hsl(var(--border-300)/.12);box-shadow:inset 0 1px 0 hsl(var(--text-000)/.04),0 1px 2px hsl(var(--always-black)/.04)}.digest-feature::before{content:\"\";position:absolute;inset:0 auto 0 0;width:4px;background:hsl(var(--accent-brand))}.dark .digest-feature{background:radial-gradient(circle,hsl(var(--text-000)/.02) 1px,transparent 1px) 0 0/18px 18px,linear-gradient(180deg,hsl(var(--bg-000)/.75),hsl(var(--bg-000)/.5));border-color:hsl(var(--border-300)/.1);box-shadow:inset 0 1px 0 hsl(var(--text-000)/.03),0 1px 2px hsl(var(--always-black)/.25)}.digest-feature>:first-child{margin-top:0}.digest-feature>:last-child{margin-bottom:0}.digest-feature-header{display:flex;align-items:center;flex-wrap:wrap;gap:.625rem;margin:0 0 .75rem}#content-container .digest-feature-title{font-family:\"Anthropic Serif Display\",Georgia,serif;font-size:1.75rem;line-height:1.15;font-weight:500;letter-spacing:-.015em;color:hsl(var(--text-000));margin:0}#content-container .digest-feature-pill{font-family:ui-monospace,\"SF Mono\",Menlo,Consolas,monospace;font-size:.75rem;line-height:1;letter-spacing:.01em;padding:.3rem .6rem;border-radius:999px;background:hsl(var(--accent-brand)/.12);color:hsl(var(--accent-main-000));border:1px solid hsl(var(--accent-brand)/.25);white-space:nowrap;transform:translateY(1px)}#content-container .digest-feature-lede{font-size:1.0625rem;line-height:1.65;color:hsl(var(--text-100));margin:0 0 1.25rem;max-width:none}#content-container .digest-feature-lede code{font-size:.875em;padding:.1em .35em}#content-container .digest-feature-try{font-size:.875rem;color:hsl(var(--text-400));margin:1.25rem 0 .5rem}#content-container .digest-feature .frame{margin:1rem 0;border-radius:0;padding:0}#content-container .digest-feature .frame>*,#content-container .digest-feature [class*=CodeBlock],#content-container .digest-feature pre{border-radius:0}#content-container .digest-feature-link{display:inline-flex;align-items:center;gap:.35rem;font-size:.875rem;font-weight:500;color:hsl(var(--accent-main-100));text-decoration:none;border-bottom:none;margin-top:.75rem}#content-container .digest-feature-link::after{content:\"→\";transition:transform 120ms ease-out}#content-container .digest-feature-link:hover::after{transform:translateX(3px)}.digest-wins{margin:2.5rem 0;padding:1.5rem 1.75rem 1.25rem;background:hsl(var(--bg-200));border:1px solid hsl(var(--border-300)/.1)}.dark .digest-wins{background:hsl(var(--bg-200)/.6)}#content-container .digest-wins-title{font-family:\"Anthropic Serif Display\",Georgia,serif;font-size:1.25rem;font-weight:500;color:hsl(var(--text-000));margin:0 0 .75rem}.digest-wins-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));column-gap:2rem}#content-container .digest-wins-grid>div{position:relative;font-size:.875rem;line-height:1.5;color:hsl(var(--text-300));padding:.5rem 0 .5rem 1.125rem;border-top:1px solid hsl(var(--border-300)/.06);margin:0}#content-container .digest-wins-grid>div::before{content:\"+\";position:absolute;left:0;top:.5rem;font-family:ui-monospace,\"SF Mono\",Menlo,Consolas,monospace;font-size:.8125rem;font-weight:600;color:hsl(var(--accent-brand))}#content-container .digest-wins-grid>div:first-child,#content-container .digest-wins-grid>div:nth-child(2){border-top:none;padding-top:0}#content-container .digest-wins-grid>div:first-

## Source (tools-reference): https://docs.claude.com/en/docs/claude-code/tools-reference

Tools reference - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Assistant
Responses are generated using AI and may contain mistakes.
Claude Code has access to a set of built-in tools that help it understand and modify your codebase. The tool names are the exact strings you use in
permission rules
,
subagent tool lists
, and
hook matchers
.
To control which tools Claude can use and when it asks first, configure
permission rules
in your settings,
hooks
, or a
subagent’s tool list
. See
Configure tools with permission rules and hooks
for each place that accepts a tool name.
To add custom tools, connect an
MCP server
. To extend Claude with reusable prompt-based workflows, write a
skill
, which runs through the existing
Skill
tool rather than adding a new tool entry.
In
auto mode
, a classifier decides most permission prompts instead of you. The
Permission required
column shows whether the tool prompts in
Manual mode
for paths inside the working directory. File-access tools marked No, including
Read
,
Grep
, and
Glob
, still prompt for paths outside the
working directory and additional directories
.
Bash
is marked Yes but runs a built-in set of
read-only commands
without prompting.
Tool
Description
Permission required
Agent
Spawns a
subagent
with its own context window to handle a task. With
agent teams
enabled, a call that carries a
name
can launch a
teammate
instead. See
Agent tool behavior
No
Artifact
Publishes an HTML or Markdown file to claude.ai as an
artifact
: a private, interactive page. You can share it with a public link, or inside your organization on Team and Enterprise plans, where public sharing requires an Owner to
enable it
. Requires a Pro, Max, Ultra, Team, or Enterprise plan and
/login
authentication; see
Availability
Yes
AskUserQuestion
Asks multiple-choice questions to gather requirements or clarify ambiguity. Questions stay open until you answer them by default. See
AskUserQuestion tool behavior
No
Bash
Executes shell commands in your environment. See
Bash tool behavior
Yes
CronCreate
Schedules a recurring or one-shot prompt within the current session. Tasks are session-scoped and restored on
--resume
or
--continue
if unexpired. See
session-scoped scheduled tasks
No
CronDelete
Cancels a session-scoped scheduled task by ID
No
CronList
Lists all session-scoped scheduled tasks
No
Edit
Makes targeted edits to specific files. See
Edit tool behavior
Yes
EndConversation
Ends the session, in rare cases of sustained abusive input or when you ask Claude to demonstrate the tool. See
EndConversation tool behavior
No
EnterPlanMode
Switches to plan mode to design an approach before coding
No
EnterWorktree
Creates an isolated
git worktree
and switches into it. Pass a
path
to switch into an existing worktree instead of creating a new one. On first entry the target may be a worktree of the current repository or, in a multi-repo workspace, of a repository nested inside it. Before v2.1.203, a nested repository’s worktree was rejected. A
path
outside
.claude/worktrees/
prompts for your approval before entering, since it moves the session’s working directory and write access to that location. New-worktree creation and paths under
.claude/worktrees/
don’t prompt. Before v2.1.206, Claude entered paths outside
.claude/worktrees/
without a prompt. From within a worktree session, or from a subagent with a pinned working directory such as
isolation: worktree
, only the
path
form is available and the target must be under
.claude/worktrees/
of the session’s repository
Yes
ExitPlanMode
Presents a plan for approval and exits plan mode
Yes
ExitWorktree
Exits a worktree session and returns to the original directory. Not available to subagents that already run in their own working directory, such as with
isolation: worktree
No
Glob
Finds files based on pattern matching. Absent by default on macOS, Linux, and WSL. See
Glob tool behavior
No
Grep
Searches for patterns in file contents. Absent by default on macOS, Linux, and WSL. See
Grep tool behavior
No
ListAgents
Lists the agents Claude can message with
SendMessage
: subagents in the session,
agent team
teammates, your other local Claude Code sessions, and, while this session is connected to
Remote Control
, your
cloud sessions
and your Remote Control sessions on other machines. Backs the
/list-agents
command. See
cross-session messaging
. Requires Claude Code v2.1.224 or later, and appears only in sessions where
cross-session messaging is enabled
. Teammate rows and the first line showing this session’s own name require v2.1.239 or later
No
ListMcpResourcesTool
Lists resources exposed by connected
MCP servers
, leaving out
MCP Apps UI resources
, which are pages for a host application to render
No
LSP
Code intelligence via language servers: jump to definitions, find references, report type errors and warnings. See
LSP tool behavior
No
Monitor
Runs a command in the background and feeds each output line back to Claude, so it can react to log entries, file changes, or polled status mid-conversation. Can also open a WebSocket and treat each incoming message as an event. See
Monitor tool
Yes
NotebookEdit
Modifies Jupyter notebook cells. See
NotebookEdit tool behavior
Yes
PowerShell
Executes PowerShell commands natively. See
PowerShell tool
for availability
Yes
PushNotification
Sends a desktop notification, and a phone push when
Remote Control
is connected, so a long-running task or
session-scoped scheduled task
can reach you when you step away. Push delivery runs through Anthropic-hosted infrastructure, which is not accessible from Amazon Bedrock, Claude Platform on AWS, Google Cloud’s Agent Platform, or Microsoft Foundry
No
Read
Reads the contents of files. See
Read tool behavior
No
ReadMcpResourceTool
Reads a specific MCP resource by URI
No
RemoteTrigger
Creates, updates, runs, and lists
cloud scheduled tasks
, formerly routines, on claude.ai. Backs the
/schedule
command. The
RemoteTrigger
input reference
documents every action and the organization policies that remove the tool. Cloud scheduled tasks live on claude.ai and require a Pro, Max, Ultra, Team, or Enterprise plan. This tool is therefore not accessible from Amazon Bedrock, Claude Platform on AWS, Google Cloud’s Agent Platform, or Microsoft Foundry
No
ReportFindings
Reports code-review findings as a structured list, with a file, summary, and failure scenario per finding, so Claude Code can render them instead of printing them as text. Claude calls it when active code-review instructions tell it to. A finding can also carry an optional
category
slug, such as
correctness
or
test-coverage
, shown next to the file location in the rendered list
No
ScheduleWakeup
Reschedules the next iteration of a
self-paced
/loop
. Claude calls this at the end of each iteration to pick when the next one runs, between one minute and one hour out; you don’t call it directly. To end the loop instead, Claude calls it with
stop: true
, which cancels the pending wakeup. The pending wakeup appears in
session_crons
in
Stop hook input
No
SendFeedback
Drafts a feedback report about Claude Code, covering a product problem or Claude’s own behavior in the session, and queues it on your machine for you to review. Claude Code sends nothing until you choose to send the draft. See
SendFeedback tool behavior
. Requires Claude Code v2.1.238 or later
No
SendMessage
Sends a message to another agent: an
agent team
teammate, a
subagent it resumes
by agent ID or name, or one of your other Claude Code sessions, on this machine or beyond it. Messaging other sessions requires Claude Code v2.1.224 or later.
Cross-session messaging
covers which sessions Claude can reach,
what a message looks like when it arrives
, and
how Claude gets a notice when another session goes idle
. Claude can include an optional
summary
input, typically 5-10 words, that Claude Code shows as a one-line preview. When Claude omits it on a
plain-text message
, Claude Code uses the first line of the message as the summary. Claude Code truncates a summary longer than 200 characters with an ellipsis
No
SendUserFile
Sends files from the session to you with an optional caption, so a generated report, diagram, screenshot, or built artifact reaches your device instead of only being mentioned in the transcript. The optional
display
input controls presentation:
render
opens the file inline in the client,
attach
shows a download card only, and when unset the client decides by file type. Available when a
Remote Control
client is connected or in a
cloud session
. Delivery runs through Anthropic-hosted infrastructure, so the tool is not available on Amazon Bedrock, Google Cloud’s Agent Platform, or Microsoft Foundry
No
ShareOnboardingGuide
Uploads
ONBOARDING.md
and returns a share link teammates can open in Claude Code. Called from
/team-onboarding
after the guide is written. Available to claude.ai subscribers on Team and Enterprise plans
Yes
Skill
Executes a
skill
within the main conversation
Yes
SubagentHandback
Delivers a subagent’s final report to whichever conversation receives that subagent’s result. Provided only in
auto mode
, to subagents that the Agent tool runs locally other than
forks
, and available in the terminal CLI, IDE extensions, cloud sessions, and the Agent SDK; the classifier reviews the report before it’s delivered. Requires Claude Code v2.1.271 or later
No
TaskCreate
Creates a new task in the task list. Provided by default only on the models listed under
Task tool availability
, and on other models when you opt in
No
TaskGet
Retrieves full details for a specific task. Provided by default only on the models listed under
Task tool availability
, and on other models when you opt in
No
TaskList
Lists all tasks with their current status. Provided by default only on the models listed under
Task tool availability
, and on other models when you opt in
No
TaskOutput
Removed in v2.1.277. Previously retrieved output from a background task; Claude reads a background task’s
output file
with
Read
instead
No
TaskStop
Stops a running background task by ID. It also accepts an
agent-team teammate
or a named background agent by agent ID or name. When no task matches the ID, the error lists the running background agents by ID and description, including agents that another agent spawned
No
TaskUpdate
Updates task status, dependencies, details, or deletes tasks. Provided by default only on the models listed under
Task tool availability
, and on other models when you opt in
No
TodoWrite
Manages the session task checklist. Disabled by default in favor of
TaskCreate
,
TaskGet
,
TaskList
, and
TaskUpdate
. Set
CLAUDE_CODE_ENABLE_TASKS=0
to re-enable it in
sessions that have the task-tracking tools
No
ToolSearch
Searches for and loads deferred tools when
tool search
is enabled
No
WaitForMcpServers
Waits for one or more
MCP servers
that are still connecting in the background, so a request can use their tools without restarting the session. Claude calls it when a needed server isn’t connected yet. Only appears when
tool search
is disabled, since
ToolSearch
handles the wait when it’s enabled
No
WebFetch
Fetches content from a specified URL. See
WebFetch tool behavior
Yes
WebSearch
Performs web searches. See
WebSearch tool behavior
Yes
Workflow
Runs a
dynamic workflow
: a script that orchestrates many subagents in the background and returns one consolidated result
Yes
Write
Creates or overwrites files. See
Write tool behavior
Yes
​
Configure tools with permission rules and hooks
For the most part, Claude decides when to use these tools and you don’t need to name them yourself when interacting with Claude. You reference tool names directly when defining permissions and other configuration:
in
permissions.allow
and
permissions.deny
in settings, and the
/permissions
interface
in the
--allowedTools
and
--disallowedTools
CLI flags
in the Agent SDK’s
allowedTools
and
disallowedTools
options
in a
skill’s
allowed-tools
frontmatter
in a hook’s
if
condition
All of these accept the same rule format,
ToolName(specifier)
. The specifier depends on the tool, and several tools share a format:
Rule format
Applies to
Details
Bash(npm run *)
Bash, Monitor
Command pattern matching
PowerShell(Get-ChildItem *)
PowerShell
Command pattern matching
Read(~/secrets/**)
Read, Grep, Glob, LSP
Path pattern matching
Edit(/src/**)
Edit, Write, NotebookEdit
Path pattern matching
Skill(deploy *)
Skill
Skill name matching
Agent(Explore)
Agent
Subagent type matching
WebFetch(domain:example.com)
WebFetch
Domain matching
WebSearch
WebSearch
No specifier; allow or deny the tool as a whole
Tools not listed here, such as
ExitPlanMode
or
ShareOnboardingGuide
, accept only the bare tool name with no specifier.
An
Edit(...)
allow rule also grants read access to the same path, so you don’t need a matching
Read(...)
rule. A
Read(...)
deny rule also blocks the Edit and Write tools on the same path, including creating a new file there, because both tools change content Claude has to be able to read back. For the Write tool, the
Read
deny check requires Claude Code v2.1.228 or later.
Hook
matcher
fields use bare tool names, not the parenthesized rule format. See
matcher patterns
for the matching rules. For the field names each tool passes to
tool_input
in hooks, see the
PreToolUse input reference
.
​
Agent tool behavior
The Agent tool spawns a subagent in a separate context window. The subagent works through its task autonomously, then returns its result to the parent conversation. The parent doesn’t see the subagent’s intermediate tool calls or outputs, only that final result. The same tool can also launch a teammate or a fork:
Teammate
: with
agent teams
enabled, a call that carries a
name
can launch a
teammate
instead, which reports back through team messages rather than by returning a result
Fork
: wherever
fork mode
is on, the tool can launch a
forked subagent
, which inherits the full parent conversation instead of starting fresh
To cap how many turns a subagent runs, set
maxTurns
in the
subagent definition
. When the subagent reaches the limit, Claude Code marks the returned result as partial output, and Claude can
resume the subagent
to continue.
Which tools a non-fork subagent can use depends on the
tools
and
disallowedTools
fields in the
subagent definition
:
Neither field set
: the subagent inherits every
tool available to subagents
.
tools
only
: the subagent gets only the listed tools.
disallowedTools
only
: the subagent gets every parent tool except the listed ones.
Both set
:
disallowedTools
takes precedence. A tool listed in both is removed.
In every case, the resolved set is limited to the
tools available to subagents
: a tool that isn’t available to subagents is never granted, even when listed in
tools
. Where the conditions in the
SubagentHandback
tools-table entry hold, Claude Code also gives the subagent that tool, even if you leave it out of
tools
or list it in
disallowedTools
.
If every entry in a subagent’s
tools
list fails to match a usable tool, the Agent tool usually returns an error naming the entries instead of launching the subagent; see
Agent would be spawned with zero tools
for the message and how to fix each entry.
Launching the subagent doesn’t itself prompt for permission. Claude Code checks the subagent’s own tool calls against your permission rules as it runs.
Where you see a subagent’s permission prompts depends on whether it runs in the foreground or the background. Claude Code runs subagents in the background by default, apart from the
cases that run in the foreground
.
Foreground subagents
show the same permission prompts you would see in the main conversation, at the moment each tool call happens.
Background subagents
surface permission prompts in your main session. The prompt names which subagent is asking, and pressing Esc denies that one tool call without stopping the subagent.
To
limit what a subagent can reach
in the first place, narrow its
tools
field, for example by leaving Bash off the list, or set deny rules in your settings.
​
AskUserQuestion tool behavior
Claude uses
AskUserQuestion
to ask you multiple-choice questions when it needs a decision or a clarification. Answer by picking an option, or type your own text through the
Other
row or the notes field.
When you answer by typing your own text, Claude Code relays the answer with neutral wording so Claude follows what you wrote, including a request to wait or explain first.
​
Question auto-continue timeout
Questions stay open until you answer them. If you want a question you leave unanswered to eventually close and let Claude continue without you, set the
askUserQuestionTimeout
setting to
60s
,
5m
, or
10m
, either in your user
settings.json
or from the
Question auto-continue timeout
row in
/config
.
After a question sits that long with no input, the dialog closes on its own: it submits any options you’d already selected and tells Claude you may be away from your keyboard, so Claude proceeds on its own judgment and can re-ask later. You see a countdown for the last 20 seconds. Press any key to restart the timer. While your terminal reports that its window is focused, the timer doesn’t count down.
The timer never starts for a question Claude asks in a
background session
, in
screen reader mode
, or while the session is connected to
Remote Control
. Those questions wait until you answer them. The timeout applies only to
AskUserQuestion
’s multiple-choice questions; permission prompts, including plan approval, never auto-resolve on idle.
​
Bash tool behavior
The Bash tool runs each command in a separate process.
​
What persists between commands
When Claude runs
cd
in the main session, the new working directory carries over to later Bash commands as long as it stays inside the project directory or an
additional working directory
you added with
--add-dir
,
/add-dir
, or
additionalDirectories
in settings. This includes commands Claude runs in response to your later messages.
Subagent sessions never carry over working directory changes.
If
cd
lands outside those directories, Claude Code resets to the project directory and appends
Shell cwd was reset to <dir>
to the tool result.
To disable this carry-over so every Bash command starts in the project directory, set
CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1
.
Environment variables don’t persist. An
export
in one command won’t be available in the next.
Aliases and shell functions defined in your shell startup file are available. At session start, Claude Code sources
~/.zshrc
,
~/.bashrc
, or
~/.profile
depending on your shell, captures the resulting aliases, functions, and shell options, and applies them to every Bash command.
Activate your virtualenv or conda environment before launching Claude Code. To make environment variables persist across Bash commands, set
CLAUDE_ENV_FILE
to a shell script before launching Claude Code, or use a
SessionStart hook
to populate it dynamically.
​
Timeout and output limits
Each command runs under a timeout, and Claude manages it: when it wants longer than the default for a command, it passes the
timeout
parameter with that call. You never set a per-command timeout.
Two
environment variables
control what Claude gets for a command that runs in the foreground:
BASH_DEFAULT_TIMEOUT_MS
— the default when Claude passes no timeout; two minutes out of the box
BASH_MAX_TIMEOUT_MS
— with the default, sets the ceiling that caps whatever Claude requests: the effective ceiling is the larger of the two, ten minutes out of the box
In a session that has a
time limit for background commands
,
timeout
on a command that Claude starts in the background instead sets how long the command may run there, with that limit’s separate default and maximum. The
PowerShell tool
follows the same timeout rules and reads the same two variables.
​
Output limits
Claude Code streams a command’s output to a working file as the command runs; a command whose output passes 5 GB is killed. When the command finishes, Claude Code reads the output back from that file, up to the read-back window described below. How much of the output reaches Claude inline depends on whether Claude Code treats the result as a failure:
Result
What Claude gets
Valid
Inline up to roughly 30,000 characters by default; past that, the path of a file saved to the session directory and truncated past 64 MiB, plus a preview of up to the first 2,000 characters, and Claude reads or searches the file when it needs the rest
Failure
Inline up to roughly 10,000 characters; past that, a head-and-tail excerpt of that size cut from the read-back window, with no file path
A command that exits 1 counts as a valid result for the Bash tool only when Claude Code recognizes exit code 1 as a benign outcome for that command:
grep
,
rg
,
egrep
,
fgrep
,
find
,
diff
,
test
, and
[
, plus
git diff
and
git grep
. Every other command that exits 1 counts as a failure, even when exit 1 is a benign informational outcome: no matches for
pgrep
and
jq -e
, files that differ for
cmp
.
BASH_MAX_OUTPUT_LENGTH
sets how many characters of output Claude Code reads back from the working file into a command’s result: 30,000 by default, up to a hard ceiling of 150,000. Raise it when your commands routinely overflow that window, such as a verbose build or a full test-suite log. Raising it enlarges the read-back window, which is also the window a failing command’s excerpt is cut from. It doesn’t raise the inline ceilings: a valid result over the inline ceiling arrives as a file path plus preview regardless of this variable.
To change how much of a valid result Claude receives inline, set the
bashOutputMaxChars
setting instead, up to 128,000 characters. It sizes the inline ceiling and the read-back window together, and Claude Code then ignores
BASH_MAX_OUTPUT_LENGTH
. Requires Claude Code v2.1.261 or later.
​
Background commands
For long-running processes such as dev servers or watch builds, Claude can set
run_in_background: true
to start the command as a background task and continue working while it runs. List and stop background tasks with
/tasks
. After you stop one there, or from a connected client such as the desktop app, Claude moves on instead of waiting for it. If a subagent started the command, it’s that subagent that moves on.
​
When a background command stops
A command that a
foreground subagent
started stops when that subagent’s run ends, whether it finished, failed, or was interrupted. A command that the main conversation or a background subagent started keeps running after a final response, until it exits, is stopped, or reaches its
time limit
.
While a command that the main conversation started is still running, a run in non-interactive mode with the
-p
flag
stays open after its result
until that command exits or reaches its time limit. A command that a background subagent started is stopped when the run exits.
​
Time limit for background commands
In a session that runs unattended, such as a run with the
-p
flag, an Agent SDK application, a CI job, or a cloud session, background Bash and PowerShell commands have a time limit. A local session you work in from a terminal, the desktop app, or the VS Code extension has no time limit on background commands.
The time limit requires Claude Code v2.1.285 or later. Before v2.1.288, it applied in every session.
The time limit counts from the moment the command enters the background:
A command that Claude starts in the background gets 30 minutes, or the
timeout
Claude passes with
run_in_background
, up to a maximum of 2 hours
A command that starts in the foreground and then moves to the background, for example at its timeout, gets 30 minutes from the move
In a run with the
-p
flag whose prompt you pass as text rather than with
--input-format stream-json
, both defaults are 10 minutes instead of 30, because the run
waits for background commands after its result
.
When a background command reaches its time limit, Claude Code stops it and tells Claude why, and Claude can start the command again with a longer
timeout
if the work still needs it. The stop notice reads
Background command "<description>" was stopped after reaching its background time limit
.
​
Raise the time limit for background commands
Two
environment variables
raise these limits, for Bash and PowerShell commands alike. Both take milliseconds, and neither can shorten a limit: a lower value leaves the defaults and the 2-hour maximum in place.
Set
BASH_DEFAULT_TIMEOUT_MS
above
1800000
to replace the 30-minute default with that value, both for commands Claude starts without a
timeout
and for moved commands. In a
-p
run whose prompt you pass as text, any value above
600000
replaces its 10-minute default
Set
BASH_MAX_TIMEOUT_MS
above
7200000
to raise the 2-hour maximum to that value. Setting
BASH_DEFAULT_TIMEOUT_MS
above
7200000
raises the maximum the same way
​
Foreground commands that move to the background
When a foreground command reaches its timeout without finishing, Claude Code moves it to the background instead of stopping it, unless the command starts with
sleep
. A moved command’s
time limit
counts from the move, and a foreground subagent’s moved command still stops when that subagent’s run ends.
Setting
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
or running in
bare mode
disables auto-backgrounding, so a command that reaches its timeout stops instead.
The result of a command moved to the background states what happened:
When the timeout triggers the move, the result reports it explicitly:
Command did not complete within its 120s timeout and was moved to the background
, with the seconds matching the timeout that applied, followed by the task ID and the path of the file the output is being written to.
A
cd
,
pushd
,
popd
, or
chdir
inside a command that is moved to the background never carries over: the result states
Session cwd remains <dir>; directory changes made by the backgrounded command do not apply to subsequent commands.
, so Claude doesn’t act on a directory change that didn’t happen.
​
Memory limit on Linux and WSL
On Linux and WSL, set
CLAUDE_CODE_TOOL_MEMORY_LIMIT
to a size such as
4G
to cap the memory that Bash, PowerShell, and
Monitor
tool commands can use, so one runaway build can’t take the memory the rest of the session needs. Requires Claude Code v2.1.233 or later. Before v2.1.246, Monitor tool commands ran outside the cap.
Write the size as a number of bytes or with a
K
,
M
,
G
, or
T
suffix. Set
0
,
off
,
false
,
no
, or
none
to turn the cap off. Claude Code ignores any other value it can’t read as a size, such as
4e9
.
Claude Code counts all of a session’s Bash, PowerShell, and Monitor commands against the one cap, not each command on its own.
Claude Code applies the cap with a memory cgroup. When it can’t set the cgroup up, commands run without a cap, and the debug log from
claude --debug
says why.
After the first process Claude Code starts has turned the cap on, or has turned it off because of an off value or a failed cgroup setup, Claude Code holds that result until you relaunch. To apply a changed or removed value, or a fixed setup, launch
claude
again.
When commands can’t stay under the cap, the kernel kills a command, and nothing in its result names the cap.
Claude Code can also count other kinds of processes it starts against the same limit. Set
CLAUDE_CODE_TOOL_MEMORY_CGROUP_EXCLUDE
to a comma-separated list of the kinds to exempt from the cap; Claude Code applies the cap to every kind not on your list. Set it to
none
to cap every kind, or to
all-new
to cap only Bash, PowerShell, and Monitor tool commands. Requires Claude Code v2.1.246 or later. The kinds you can name:
mcp
: local
MCP servers
lsp
:
language servers
hooks
:
hook
commands
plugin
: commands that
plugins
run
helper
: Claude Code’s own helper commands, such as
git
agent
: child Claude Code processes, such as
agent teammates
Whatever you list, these rules apply:
Unknown names
: Claude Code ignores names it doesn’t recognize
Variable unset
: Claude Code takes the set of other capped kinds from configuration Anthropic delivers from the server, and that set can change over time, so set the variable when you need a set that doesn’t change
Permission-gating hooks
: even with every kind capped, Claude Code excludes from the cap a hook that can block or change the outcome of an action, and any MCP server that such a hook calls, so the kernel killing a permission-gating hook can’t allow the action it was blocking
​
Edit tool behavior
The Edit tool performs exact string replacement. It takes an
old_string
and a
new_string
and replaces the first with the second. It doesn’t use regex or fuzzy matching.
These checks must pass for an edit to apply. Before any of them, a path matched by a
Read
deny rule
is refused, including creating a new file there.
Read-before-edit
: Claude reads the file in the current conversation before editing it, and a read cut short with a
PARTIAL view
notice
doesn’t count. Claude Opus 4.6, Claude Haiku 4.5, and older models always require the read. Newer models can edit an unread file when reading it wouldn’t need a permission prompt and the Read tool is available.
Match
:
old_string
must appear in the file exactly as written. A single character of whitespace or indentation difference is enough to miss.
Uniqueness
:
old_string
must appear exactly once. When it appears more than once, Claude either supplies a longer string with enough surrounding context to pin down one occurrence, or sets
replace_all: true
to replace them all.
A file that changed on disk after Claude last read it can still be edited when
old_string
matches the current content exactly and unambiguously and Claude Code can read the file without prompting. Matching against the file’s current content keeps this safe, and the result notes that the file carries other changes so Claude re-reads it before edits that depend on surrounding content. In any other case, such as a stale
old_string
or one that matches more than once without
replace_all
, Claude reads the file again before editing.
Claude can also edit a file without a separate Read after viewing it with a Bash command such as
cat
or
grep
. Those commands are
cat
,
nl
,
bat
,
batcat
,
head
,
tail
,
sed -n 'X,Yp'
,
grep
,
egrep
,
fgrep
, and
rg
, each run on one file with no pipes or redirects. If the command printed none of the file’s text, as when a search matches nothing, the read-before-edit check still applies.
When Claude views a file this way, Claude Code also loads any
subdirectory
CLAUDE.md
and
path-scoped rules
that apply to that file. See
Read and Edit permission rules
for which Bash commands your
Read
and
Edit
deny rules cover.
​
Non-UTF-8 files
Claude can’t use
NotebookEdit
on a file that isn’t valid UTF-8. The same goes for Edit, unless the file starts with a little-endian UTF-16 byte-order mark. When Claude tries, the tool refuses the change and leaves the file untouched. Refused files include non-ASCII text saved in a legacy encoding such as Windows-1252 or Shift-JIS, binary files, and UTF-8 with an invalid byte sequence.
The tools refuse because they save the whole file back as UTF-8, which would replace every byte they can’t decode with the replacement character
U+FFFD
. Instead, the
error Claude receives
tells it to make the change with a shell command that keeps the file’s encoding, or to ask you about converting it to UTF-8 first.
Claude can still replace such a file with Write, unless the new content contains
U+FFFD
, the character Read shows Claude in place of bytes it can’t decode. That guard stops Claude from writing back the garbled text it read. When Write does replace the file, it saves the new content as UTF-8, so the file’s original encoding is lost.
​
EndConversation tool behavior
The EndConversation tool ends the current session. Claude uses it only in two situations:
as a last resort against sustained abusive input, after attempts to redirect the conversation have failed and after a clear warning in an earlier message
when you explicitly ask to see the tool demonstrated and confirm that you want the session to end
General frustration, profanity, or a task going badly don’t qualify, and neither do requests for harmful content, which Claude declines instead of ending the session. Claude Code follows the same approach as claude.ai, which can
end a rare subset of chats
.
After Claude ends an interactive session, the session locks. New prompts and most commands return
Claude ended this conversation. Start a new session (or /clear) to continue.
, and only
/clear
,
/resume
,
/help
,
/exit
, and
/feedback
still run. Claude Code records the end in the session’s transcript, so resuming an ended session restores the lock; the session’s history isn’t deleted.
Resuming an ended session in
non-interactive mode
with the
-p
flag errors and exits with code 1, so a script doesn’t read the ended run as a success.
The tool never prompts for permission, and
PreToolUse hooks
don’t run for it. While any other tool remains, you can’t block it either:
deny and ask rules
naming
EndConversation
have no effect, and neither
--disallowedTools
nor a
--tools
list can remove it. The exemption is deliberate: the tool does nothing except end the conversation, never reading or modifying files or data, and a safeguard of this kind holds only if the session it applies to can’t turn it off. When your deny rules remove every other tool and also match
EndConversation
, as
"*"
does, Claude Code removes it too rather than leaving it as the only tool, unless an allow rule names
EndConversation
explicitly. A deny list that removes every other tool without matching
EndConversation
leaves it in place.
Subagents
never get the tool. Background tasks that share the main conversation’s tool list see it, but calling it there ends nothing.
The tool appears only when all of the following are true:
Model
: the session’s model is Claude Opus 4.8, Claude Sonnet 5, Claude Fable 5, or a later version of one of those families.
Surface
: an interactive terminal session, including a
claude
session in an IDE’s integrated terminal, which is how the
JetBrains plugin
runs it. Other surfaces don’t include the tool, such as:
non-interactive
-p
runs
sessions through the
Agent SDK
TypeScript and Python packages
the
VS Code extension
panel, which bundles its own CLI
GitHub Actions
cloud sessions
Startup mode
: not a
--bare
session. Bare mode loads only shell and file tools, so the tool is never registered there.
Provider
: not available on
Amazon Bedrock
,
Claude Platform on AWS
,
Google Cloud’s Agent Platform
, or
Microsoft Foundry
, or on sessions signed in through a
cloud gateway
.
​
Glob tool behavior
The Glob tool finds files by name pattern. On Windows, it’s part of the default tool set. On macOS, Linux, and WSL, Claude Code leaves Glob and
Grep
out of the default tool set, and Claude searches with
find
and
grep
through the Bash tool instead. In Claude’s shell those two commands run embedded versions of
bfs
and
ugrep
, and the searches reach your hooks and permission rules as
Bash
calls.
On macOS, Linux, and WSL, you get the Glob and Grep tools back in these cases:
You name
Glob
or
Grep
in
--tools
or
--allowedTools
when you start the session, or in the equivalent
Agent SDK
options. With
--tools
you get the ones you list, and naming either tool in
--allowedTools
restores both. An allow rule in a settings file doesn’t have this effect.
A permissions
deny rule
, the
--disallowedTools
flag, or
--restricted
removes
Bash
from the session.
A
subagent
lists
Glob
or
Grep
in its
tools
field and leaves out
Bash
. The listed tools come back for that subagent only, or for the whole session when it runs as the main session agent through
--agent
or the
agent
setting.
Glob supports standard glob syntax including
**
for recursive directory matching:
**/*.js
matches all
.js
files at any depth
src/**/*.ts
matches all
.ts
files under
src/
*.{json,yaml}
matches
.json
and
.yaml
files in the current directory
Results are sorted by modification time and capped at 100 files. If the cap is hit, Claude sees a truncation flag in the result and can narrow the pattern.
Glob doesn’t respect
.gitignore
by default, so it finds gitignored files alongside tracked ones. This differs from
Grep
, which skips gitignored files. To make Glob respect
.gitignore
, set
CLAUDE_CODE_GLOB_NO_IGNORE=false
before launching Claude Code.
Claude Code decides permission for a Glob call before it checks whether the search directory exists. It still runs the read-permission check for a missing
path
outside the
working directories
, so a permission prompt for a path doesn’t mean the path exists.
A
pattern
or
path
value that contains a null byte returns an error asking Claude to remove it.
​
Grep tool behavior
The Grep tool searches file contents for patterns. Where
Glob
finds files by name, Grep finds lines inside them. On macOS, Linux, and WSL, Grep is absent by default under the same conditions as Glob. See
Glob tool behavior
for when both tools are available.
Grep is built on
ripgrep
and uses ripgrep’s regex syntax, not POSIX grep. Patterns that include regex metacharacters need escaping. For example, finding
interface{}
in Go code takes the pattern
interface\{\}
.
A pattern, glob, or file type that ripgrep rejects returns an error that includes ripgrep’s diagnostic, so Claude can correct the input and search again. Before v2.1.208, Claude Code reported a rejected input as
No files found
instead of an error, even when the searched-for text existed in the target files.
Three output modes control what comes back:
files_with_matches
: file paths only, no line content. This is the default.
content
: matching lines with file and line number. When the tool’s
offset
parameter points past the last match for a pattern that has matches, Grep returns
No entries at this offset
, so Claude widens or resets the offset instead of concluding the pattern doesn’t match.
count
: match count per file, followed by a total across all matching files. The total covers every match even when the tool’s
head_limit
or
offset
parameters truncate the listed per-file entries.
Claude can scope results by file with the
glob
parameter, such as
**/*.tsx
, or by language with the
type
parameter, such as
py
or
rust
. By default, patterns match within a single line. Claude can set
multiline: true
to match across line boundaries.
Grep respects
.gitignore
, so gitignored files are skipped. To search a gitignored file, Claude passes its path directly.
Claude Code decides permission for a Grep call before it checks whether the search
path
exists. It still runs the read-permission check for a missing
path
outside the
working directories
, so a permission prompt for a path doesn’t mean the path exists.
​
LSP tool behavior
The LSP tool gives Claude code intelligence from a running language server. After each file edit, it automatically reports type errors and warnings so Claude can fix issues without a separate build step. Claude can also call it directly to navigate code:
Jump to a symbol’s definition
Find all references to a symbol
Get type information at a position
List symbols in a file
Search for a symbol by name across the workspace
Find implementations of an interface
Trace call hierarchies
Claude Code keeps the tool inactive until you install a
code intelligence plugin
for your language. In
cloud sessions
, Claude Code doesn’t start plugin language servers, so the LSP tool stays inactive there. Claude Code takes the language server’s configuration from the plugin, and you install the server binary yourself.
Claude Code returns an error result for each LSP call on a file whose language server it can’t start.
​
Monitor tool
The Monitor tool lets Claude watch something in the background and react when it changes, without pausing the conversation. Ask Claude to:
Tail a log file and flag errors as they appear
Poll a PR or CI job and report when its status changes
Watch a directory for file changes
Track output from any long-running script you point it at
Connect to a WebSocket feed and report each message as it arrives
For most watches, Claude writes a small script, runs it in the background, and receives each output line as it arrives. For a server that already pushes events, Claude can open a
WebSocket
instead of running a script.
You keep working in the same session and Claude interjects when an event arrives.
Every watch Claude starts has a deadline: 5 minutes by default, at most 30 minutes, and at most 10 minutes in a
non-interactive
run given a single prompt with
-p
.
At the deadline the watch ends. Claude gets one notice, so it can start the watch again if it’s still needed.
Stop a monitor by asking Claude to cancel it or by ending the session. When you stop a
subagent
that started monitors, for example from
/tasks
, those monitors stop with it.
When Monitor runs a command, it uses the same
permission rules as Bash
, so
allow
and
deny
patterns you have set for Bash apply here too. While
auto mode
is active, Claude Code sets aside allow rules that name
Monitor
itself, along with the other
broad allow rules it drops
, so the classifier reviews Monitor commands the same way it reviews Bash commands.
The
WebSocket source
has its own approval prompt, which the classifier also decides in auto mode.
Monitor needs a minimum version or Git Bash in these cases:
Minimum version
: on Amazon Bedrock, Claude Platform on AWS, Google Cloud’s Agent Platform, or Microsoft Foundry, or with
DISABLE_TELEMETRY
or
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
set, Monitor requires Claude Code v2.1.310 or later. The requirement applies when
feature-flag fetching
is off
Windows
: the tool is available only when
Git Bash
is installed
Plugins can declare monitors that start automatically when the plugin is active, instead of asking Claude to start them. See
plugin monitors
.
​
WebSocket source
When a server already pushes events over a WebSocket, Claude can connect to it directly instead of writing a polling script. Each kind of socket activity either becomes an event or ends the watch:
Text messages
: each one becomes one event, even when the message spans multiple lines.
Binary messages
: not passed through. Claude receives a placeholder line such as
[binary frame, 512 bytes]
instead.
Messages larger than 1 MiB
: the watch ends, so subscribe to a filtered feed where one exists.
Socket close
: the watch ends and Claude receives the close code.
A WebSocket watch takes a
ws
input in place of
command
, and a single Monitor call can’t combine the two. The
ws
input has two fields:
Field
Required
Description
url
Yes
The endpoint to connect to. Must be a
ws://
or
wss://
URL with no embedded credentials or whitespace, using ASCII characters only
protocols
No
WebSocket subprotocol names to offer during the handshake. Each entry must be a valid subprotocol token, and the list can’t contain duplicates
The
timeout_ms
deadline applies to a WebSocket watch too: the watch ends at the deadline, and
TaskStop
cancels it early.
Opening a WebSocket prompts for approval; in
auto mode
the classifier decides instead. The prompt doesn’t offer an option to skip future prompts for the same host.
Claude Code denies URLs that point at a private, link-local, or cloud-metadata address, including hostnames that resolve to one. It also denies hosts in
sandbox.network.deniedDomains
, and when
allowManagedDomainsOnly
is set in managed settings, any host outside the managed allowlist.
​
NotebookEdit tool behavior
NotebookEdit modifies a Jupyter notebook one cell at a time, targeting cells by their
cell_id
. It doesn’t perform string replacement across the notebook the way
Edit
does on plain files.
Three edit modes control what happens to the target cell:
replace
: overwrite the cell’s source. This is the default.
insert
: add a new cell after the target. With no
cell_id
, the new cell goes at the start of the notebook. Requires
cell_type
set to
code
or
markdown
.
delete
: remove the target cell.
NotebookEdit refuses a notebook file that doesn’t decode as UTF-8, under the
same rule as Edit
, and writes nothing.
Permission rules use the
Edit(...)
path format. A rule like
Edit(notebooks/**)
covers NotebookEdit calls on files in that directory.
​
PowerShell tool
The PowerShell tool lets Claude run PowerShell commands natively. On Windows, this means commands run in PowerShell instead of routing through Git Bash. How the tool becomes available depends on your platform:
Windows without Git Bash
: the tool is enabled automatically.
Windows with Git Bash installed
: the tool is on by default for claude.ai and Console accounts; set
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
to enable it in Amazon Bedrock, Google Cloud’s Agent Platform, and Microsoft Foundry sessions, or
0
to turn it off.
Linux, macOS, and WSL
: the tool is opt-in.
Your
PreToolUse hooks
receive the tool’s command string in
tool_input.command
, with the same fields as the Bash tool.
Match
Bash|PowerShell
in hooks that inspect shell commands; the
PowerShell hook input section
explains why matching
Bash
alone is not enough.
​
Enable the PowerShell tool
Set
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
in your environment or in
settings.json
:
{
"env"
: {
"CLAUDE_CODE_USE_POWERSHELL_TOOL"
:
"1"
}
}
On Windows, set the variable to
0
to turn the tool off. On Linux, macOS, and WSL, the tool requires PowerShell 7 or later: install
pwsh
and ensure it is on your
PATH
.
On Windows, Claude Code auto-detects
pwsh.exe
for PowerShell 7+ with a fallback to
powershell.exe
for PowerShell 5.1. When the tool is enabled, Claude treats PowerShell as the primary shell. The Bash tool remains available for POSIX scripts when Git Bash is installed.
Claude Code spawns PowerShell with
-ExecutionPolicy Bypass
at process scope only, so
.ps1
scripts and module imports work on default Windows installs without changing the machine’s policy. Process-scope bypass doesn’t override Group Policy
MachinePolicy
or
UserPolicy
, so enterprise policies still apply. To respect the machine’s effective execution policy instead, set
CLAUDE_CODE_POWERSHELL_RESPECT_EXECUTION_POLICY=1
.
​
Bash deny rules also turn off the PowerShell tool
On Windows with Git Bash installed, denying Bash also turns the PowerShell tool off for the session. This applies to scoped rules such as
Bash(git push *)
as well as a bare
Bash
, and to rules from one of your settings files or
--disallowedTools
. Claude Code does this because a
Bash
rule doesn’t restrict the PowerShell tool, which has
its own permission rules
. With PowerShell left on, Claude could run there what your rule denies in Bash.
To keep the PowerShell tool on alongside a Bash deny rule, do either of these:
Set
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
in your environment or in the
env
block of a settings file, as shown in
Enable the PowerShell tool
.
Add a scoped
PowerShell
permission rule
to a settings file, such as a
PowerShell(git push *)
deny rule.
Without one of these, a scoped Bash deny rule leaves the Bash tool available, and Claude Code turns PowerShell off without a warning. A rule that removes the whole Bash tool leaves Claude with no shell tool for the session.
​
Shell selection in settings, hooks, and skills
Three additional settings control where PowerShell is used:
"defaultShell": "powershell"
in
settings.json
: routes interactive
!
commands through PowerShell. Requires the PowerShell tool to be enabled.
"shell": "powershell"
on individual
command hooks
: runs that hook in PowerShell. Hooks spawn PowerShell directly, so this works regardless of
CLAUDE_CODE_USE_POWERSHELL_TOOL
.
shell: powershell
in
skill frontmatter
: runs
!`command`
blocks in PowerShell. Requires the PowerShell tool to be enabled.
PowerShell commands follow the
same main-session working-directory reset behavior
as Bash commands, including the
CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR
environment variable.
PowerShell commands also receive the variables hooks persist through
CLAUDE_ENV_FILE
, under the conditions in
Persisted variables in PowerShell commands
. Requires Claude Code v2.1.296 or later.
​
Exit code 1 from searches and
git diff
in PowerShell
If a
grep
or
rg
search that matches nothing shows
Error: Exit code 1
when Claude runs it in the PowerShell tool, the search didn’t fail. You don’t need to do anything. The error can appear when the search is part of a longer command. For example, when
rg
exits with code 1,
rg foo | Out-Null
shows the error and
rg foo
doesn’t.
The PowerShell tool can count exit code 1 as a normal result from
grep
,
rg
,
egrep
,
fgrep
,
findstr
,
git grep
, and
git diff
. The searches use exit code 1 to report no matches. From
git diff
, exit code 1 means the files differ. A command that shows the error when Claude runs it
counts as failed
in a skill with
shell: powershell
.
​
Windows encoding and exit codes
Redirection with
>
and
>>
writes UTF-8 files on PowerShell 5.1
Claude Code encodes text piped to a native command’s standard input as UTF-8
Claude Code captures error output without ANSI escape sequences
A command whose child process waits on standard input receives end-of-file instead of hanging
If
where.exe
finds no match, or
fc.exe
or
diff.exe
finds that the files differ, the result can show
Error: Exit code 1
though the command didn’t fail. You don’t need to do anything.
If a
robocopy
exit code from 1 through 7 shows as an error, the copy didn’t fail and you don’t need to do anything.
robocopy
exits with code 0 through 7 to report a result, such as files copied, and with 8 or higher when it fails.
​
Preview limitations
The PowerShell tool has the following known limitations during the preview:
PowerShell profiles are not loaded
On Windows, sandboxing is not supported
​
Read tool behavior
The Read tool takes a file path and returns the contents with line numbers. Claude is instructe

## Source (changelog): https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md

# Changelog

## 2.1.316

- Added `CLAUDE_CODE_DISABLE_ULTRATHINK`, which turns the `ultrathink` keyword off
- Added pooled group budgets to the Claude apps gateway: one monthly budget that a group's members share, on top of each member's own limit, set with `pooled_budget` on the spend limits admin API
- Added `CLAUDE_CODE_DISABLE_LOOPED_CROSS_CERT_DROP` to keep system cross-certificates that certify each other in a loop, for servers whose private CA needs one
- Added `CLAUDE_CODE_SUBAGENT_EFFORT` to set the effort level subagents run at when nothing else names one, instead of inheriting the session's
- Added `managed.policy_mode: layered` to the Claude apps gateway: every policy that matches a developer applies, each merged over the ones listed below it, not only the first
- Added `guardrail.input_tagging` on Claude apps gateway Bedrock upstreams, which wraps prompts in the input tags that an Amazon Bedrock guardrail's prompt attacks filter needs; `all_messages_and_system` also tags the system prompt
- Deprecated fast mode for Opus 4.8 as of October 30, 2026; it will be removed on November 30, 2026. After removal, fast mode requests on Opus 4.8 return an error and do not fall back to standard Opus 4.8. Migrate to Opus 5.5 to keep the speedup
- Fixed shell commands being left running on macOS and Linux when Claude Code exits by itself, for example when credentials are refused or a cloud session is archived
- Fixed bash aliases with line breaks in their value (except in Git Bash), and functions whose names start with a dash, being garbled or lost in the Bash tool's shell
- Fixed bash scripts started from the Bash tool stopping after their first command when `SHELLOPTS` is exported
- Fixed PowerShell hooks not blocking on exit code 2 when the command begins with a type cast, `param`, `using` or an attribute
- Fixed some network requests hanging when a compressed response was cut off or corrupted
- Fixed `sonnet`, `opus` and `haiku` on Vertex AI and Amazon Bedrock showing an error mid-session instead of switching to an older model when the newest is not yet available to the account or region
- Fixed the Claude apps gateway not checking every model a request names against `availableModels`, `deniedModels` and `models`; a request that names a blocked model now gets a 400 naming the field
- Fixed `claude auth login` refusing to run where managed settings require a Claude apps gateway; in a terminal it now shows the gateway sign-in
- Fixed `--restricted` sessions uploading files from outside the working directories when a Read allow rule covered them
- Fixed prompts containing invisible characters needing a second Enter to send; plain prompts now send cleaned on the first Enter, and commands still wait for review
- Fixed sub-agents that inherited a parent sub-agent's model moving to the main model when a background job or message woke them
- Fixed a managed `autoMode.allow` list without `"$defaults"` getting the built-in exceptions back from a host app's `--settings`, a first rule added in `/permissions`, or `/auto-mode-setup`
- Fixed cloud sessions and cloud scheduled tasks not being marked as failed when auto mode stopped a turn because the server returned no safety verdict
- Fixed `claude -p` text output sometimes not saying why auto mode stopped a turn when a background agent was still running
- Fixed `CLAUDE_CODE_AUTO_MODE_SERVER=1` being ignored in sessions started by a host application (such as Claude Desktop) behind a proxy or LLM gateway with experimental betas turned off
- Fixed plugin MCP `headersHelper` scripts receiving a corrupted `CLAUDE_PLUGIN_ROOT` and server URL when a credential-named environment variable was set to a switch value such as `1`
- Fixed the SDK `register_repo_root` control request not loading the CLAUDE.md of a directory outside the working directory (with `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`)
- Fixed the Artifact tool showing `?` for artifact database access rules at the `self` level, and not quoting those rules back when it refuses a republish that would drop them
- Fixed `/model
` not warning when the model isn't recognized by this version and auto-compact will assume a 200K context window
- Fixed the "hold space to speak" hint using up its three showings in one session, and showing an empty key when push-to-talk is unbound
- Fixed Grep and Glob never returning when the search process is killed at the timeout but does not exit, seen on Windows
- Fixed a rare case where resuming a conversation did not restore its plan, when `/clear` or `/resume` had been run while part of that conversation was still being saved
- Fixed first-run setup dropping words from the security notes and the terminal-setup explanation in narrow terminals
- Fixed the Enterprise survey card taking a typed 1 or 0 after a short pause; a typed answer now needs Enter
- Self-hosted runner: Fixed a message sent while Claude was working being answered after a Stop, once the session's process had been replaced
- Self-hosted runner: Fixed an MCP server's on/off switch sometimes being lost when a session moved to a new machine
- Windows: Fixed the Bash tool losing your aliases and functions in Git Bash when the rc file sets errexit and pipefail and only winpty aliases, or none, are defined
- Improved `/code-review` started from the Code tab in Claude Desktop or on the web: cloud and `claude remote-control` sessions now show the findings card, not a plain-text list
- Improved `/diff` on large repositories: each refresh usually runs one fewer full-repository git command, and refreshes are spaced out when git is slow
- Improved the messages shown when `/ultrareview`, a cloud session or a cloud agent finds no GitHub remote: they now say to create a repository at https://github.com/new, and `/ultrareview` no longer suggests a `gh` command that `gh` rejects
- Improved SSL certificate errors to name the likely causes, among them a server that leaves out an intermediate certificate, and the fix for each
- Changed auto mode so that an `autoMode.allow` list without `"$defaults"` no longer removes the built-in rule on scheduled-task prompts
- Changed server-managed settings for Team and Enterprise logins: settings fetched from Anthropic's API now apply without an approval prompt, and a stored copy that doesn't verify is refused
- [VSCode] Added sign-in to a Claude apps gateway from the chat panel, with no terminal needed
- [VSCode] Changed `ultrathink` to run its turn at `xhigh` effort and show in a rainbow in the chat box, as in the terminal
- [VSCode] Fixed the missing Effort slider, Ultracode switch and model name when the model setting has the `[1m]` tag, such as `opus[1m]`
- [VSCode] Fixed saved `/btw` side-question history being deleted too early while a settings file has errors
- [VSCode] Fixed a conversation coming back in Auto mode after a reload or restart when its plan was approved with "Yes, and manually approve edits"
- [Cloud sessions] Added a form card to cloud sessions, so you can fill in or decline a form an MCP server asks for instead of the request being canceled without you seeing it
- [Cloud sessions] Added a "Catching up…" line that shows while a cloud or Remote Control session you switch back to is still bringing its messages up to date
- [Cloud sessions] Changed network secrets so Enterprise members can add and delete them on their own cloud environments, instead of only viewing them
- [Cloud sessions] Improved the Changes pane for cloud sessions: the note about what the list leaves out is now a badge beside the branch name, not a row above the diff
- [Cloud sessions] Fixed file search in a cloud session's Files pane showing folders as ../.. paths after Claude changed directory; results now show their path from the project's root
- [Claude Tag] Fixed Claude refusing to edit or append to a canvas it made in a Slack channel, from that channel, once the canvas was also shared to another channel or a DM
- [Claude Tag] Fixed untagged replies going unanswered in a Slack Connect thread when both organizations have installed Claude and Slack delivered the reply to the other organization's app
- [Claude Tag] Fixed a cloud scheduled task's live status checklist in Slack staying half-done; a run can now edit the top-level messages it posted during that run
- [Claude Tag] Changed a Slack channel's Respond automatically switch to a "How Claude participates" choice on the channel's Configure page and in Claude Tag admin settings
- [Code Review] Added a findings-by-severity card to the Code Review analytics page, showing the period's total findings, a daily chart stacked by severity, and each severity's count

## 2.1.314

- Added `permissions.blockWritesOutsideWorkingDirectories`: Write, Edit and NotebookEdit refuse paths outside the working directories in every permission mode
- Added an optional `groups` list to Claude apps gateway upstreams: only developers in the listed IdP groups are sent to that upstream, on failover too
- Added `guardrail_trace` to Claude apps gateway Bedrock upstreams, to log which Amazon Bedrock guardrail filter fired on a request, without the matched text
- Added idle compaction to VS Code and Claude Desktop's Code tab: a 200K+ token conversation left idle is summarized, and the summary is used on your next message if the prompt cache has expired
- Fixed sessions failing turn after turn with "Invalid effort level" when an organization's admin caps a model's effort: Claude Code now lowers the effort, retries, and says which level it uses
- Fixed `claude -p` exiting with code 0 and no output when startup failed; it now prints the error and exits 1
- Fixed Bedrock sessions with many images failing every turn and `/compact` with "400 Input is too long." instead of removing older images and compacting
- Fixed Microsoft Foundry sessions failing when the resource has no deployment for the default Sonnet, Opus or Haiku model: Claude Code now falls back to an older model of that family
- Fixed repeated refused requests behind a gateway that doesn't accept tool search's `tool_reference` blocks: the request is sent again once without tool search, and the session remembers
- Fixed TLS connections failing with `UNABLE_TO_GET_ISSUER_CERT` when the system certificate store holds a renewed root certificate that is cross-signed with its predecessor
- Fixed MCP servers that also work without sign-in showing "needs authentication" after their stored sign-in stopped working; they are now used signed out
- Fixed `claude mcp logout` reporting success when the MCP sign-in was not removed, for example while the macOS keychain is locked over SSH
- Fixed extra sign-in renewals when several sessions share an Anthropic profile login and the credentials lock is busy
- Fixed `claude ultrareview` and `claude remote-control` asking the workspace trust question in a CI job that has a terminal; with `CI` set they now refuse an untrusted folder at once
- Fixed an administrator's TLS trust settings in managed settings not being applied in Claude Desktop sessions
- Fixed model switching being refused on machines with managed plugin settings when one of your own `--plugin-dir` or `--plugin-url` plugins had a broken manifest or failed to download
- Fixed the Bedrock and Vertex model upgrade offer coming back at every start when managed settings pin the model
- Fixed `forceRemoteSettingsRefresh` set only in remote managed settings no longer applying once the stored copy had expired, which let sessions start without policy when the server could not be reached
- Fixed "Continue automatically at usage limit" continuing more than three times without a prompt from you when a task restarted itself between waits (a /goal check-in, a background or scheduled task)
- Fixed background and cloud sessions started with Ultracode turning it back on at their next start after it had been switched off
- Fixed the last broken reply and its retry prompts staying in the conversation after Claude gave up on a tool call that could not be parsed
- Fixed a PreCompact hook with very large output making compaction fail or repeat; each hook's output is now cut at 10,000 characters
- Fixed background diff refreshes briefly taking the repository's index lock, which could make a git command run at the same moment fail with "Unable to create '.git/index.lock': File exists"
- Fixed markdown tables jumping between grid and stacked layouts on half-typed rows while streaming, and long tables falling back to raw pipes
- Fixed the /resume picker showing the text of CLAUDE.md or CLAUDE.local.md as a session's title when the session only ran slash commands
- Fixed `/btw` answering from the main conversation when asked from a subagent's open transcript
- Fixed pasting an image over SSH to a Linux machine doing nothing silently; the prompt now says to copy the file over and paste its path
- Fixed `claude remote-control` sessions that failed to start when the session service was slow for a moment: the worker's registration is now retried with growing waits
- Fixed model switches over Remote Control that take over 8 seconds getting a "still pending" error instead of the final result
- Fixed the `sandbox.excludedCommands` setting description saying listed commands always run outside the sandbox; it now says every command in a call must match an entry
- Fixed shell and MCP calls that auto mode, a deny rule or a PreToolUse hook blocked, or that otherwise did not run, reading as if they ran in a collapsed tool group
- Fixed sandbox protections not applying to a worktree entered by `claude -p --resume` or `--continue`
- Fixed hooks matching Bash not running on shell commands started by the Monitor tool; such hooks can block or ask, but not approve or rewrite those commands
- Fixed a settings file excluded with `--setting-sources` still supplying some settings, such as auto mode rules and saved permission consents
- Fixed auto mode reporting a call as blocked, and listing it in `/permissions`, when its safety check gave no verdict
- Fixed a Claude apps gateway Vertex upstream hanging for minutes when a Google token endpoint accepts the connection and never answers
- Fixed the Claude apps gateway's start-up warning for a deprecated Claude Desktop key that it still serves as written saying "stops being accepted" after the key's end date
- Fixed `/upgrade` opening the browser and starting a new login for plans billed through the App Store or Google Play; it now says where to change the plan
- Fixed `--resume`, and rewinding past a switch to another model after a refusal, moving a session on a model name Claude Code doesn't recognize to a different model
- Fixed requests failing when a gateway or cloud provider refuses one of Claude Code's beta headers by name: the request is sent again without it
- Fixed model IDs spelled with a dot behind an LLM gateway, such as `claude-opus-4.8`, being treated as an older model with the wrong context window, output limit, effort, thinking mode and cost
- Fixed Remote Control clients showing a stray "Compacted (ctrl+o to see full summary)" row after /compact
- Fixed the cloud sessions tip and the Remote Control idle notice showing when an organization's policy turns those features off
- Fixed a resumed claude.ai cloud session making a model call nobody asked for when the previous worker stopped just after receiving a new chat's files
- Fixed WebFetch in Cowork cloud sessions silently dropping a PDF's text past 100,000 characters; it now says how much was unread and where to read on
- Fixed Claude being told only that a command was declined after you stopped it with Esc or Stop in a cloud session or the IDE; it now also hears that the command may have run
- Fixed blank lines at the top of a code block disappearing when the code block opens a quote
- Fixed a blank line appearing above some `⎿` rows in the transcript view (Ctrl+O)
- Fixed vim mode `dw`, `dW`, `yw` and `yW` carrying on past the end of the line, and made `w` and `W` stop on empty lines
- Fixed x and Enter in the agent panel sometimes acting on the wrong agent when another agent started or finished
- Fixed pasted text and dragged-in files being lost in Claude's question dialog unless the "Other" row had focus
- Fixed pasted text being lost when a row in the prompt footer was selected
- Fixed vim mode `p` over a character selection ignoring whether the yanked text was whole lines
- Fixed vim mode `aw` and `iw` taking the line break at the end of a line
- Fixed ↓ selecting footer items hidden by the ? help menu, the command list or a paste hint
- Fixed Esc on a command's panel, such as `/btw`, also interrupting the subagent whose transcript is open
- Fixed the welcome header in fullscreen mode showing the session's model while viewing a subagent or teammate that runs on a different model
- Fixed the fullscreen transcript being left mid-conversation after "Restore conversation" in the rewind menu while scrolled up
- Fixed a rare case where a deleted session could reappear in the resume list as an almost empty entry
- Fixed prompts containing tags such as `
` or `
` not being acknowledged to a local stream-json host
- Fixed sessions staying untitled when the first prompt failed (for example on a usage limit) and the conversation continued afterward
- Fixed the skill file watcher checking every removed skill kept in `~/.claude/skills/.trash`, which added file system load that grew with each removal
- Fixed the session name from /rename disappearing while Claude asks for permission or a plan decision, so side-by-side sessions stay identifiable
- Fixed background sessions that fail to start being reported as a deleted daemon binary when the binary is still on disk
- Fixed the tip and idle reminder about push notifications appearing when the push settings in `/config` are hidden or your organization has turned off Remote Control
- Fixed `~/.claude/skills/.trash` and `~/.claude/plugins/.trash` growing without limit: each now holds about 1024 entries, whatever `cleanupPeriodDays` says
- Fixed the Bash edit diff listing a whole file as changed when a CRLF file under git's line-ending conversion was re-saved unchanged or had one line edited
- Self-hosted runner: Fixed an idle session moving to another runner instead of pausing when the runner's request to pause it lost its connection before Anthropic answered
- Improved memory use in long headless and SDK turns that run many subagents: the parent session no longer keeps each subagent's tool results until the turn ends
- Improved prompt history: Ctrl+R now matches text inside collapsed `[Pasted text]` pills
- Improved the `/design-sync` upload prompt to show the folder, the project and the files it will upload or delete
- Improved `/permissions` review tab, now called Recently blocked: the footer says what Esc will do with marked rows
- Improved auto mode's blocked calls: messages name the command, say Claude may retry and auto mode checks again, and point to `/permissions` to review
- Improved permission prompts: a long reason takes fewer rows, so it pushes the command being approved off the screen on fewer terminals
- Improved the cloud session error shown while a request refused for your claude.ai login is still being retried: it now also suggests `claude auth login`
- Improved the behavior of stored claude.ai, Team, and Enterprise logins when MDM and remote settings differ on base URL or `apiKeyHelper`
- Improved `/config` in agent view to say how to stop agent view opening by default
- Improved session auto-titles: a session that starts with a skill or a prompt-based command such as `/security-review` now gets a title from it instead of staying untitled
- Improved `--resume` speed and memory use on damaged transcripts
- Improved `/context` speed in sessions with ten thousand or more MCP tools
- Self-hosted runner: Improved the error shown when a session's branch isn't on the git remote: it now covers a never-pushed branch, says how to fix each case, and no longer suggests retrying
- Updated the `/claude-api` skill: its Datadog setup for API tracing now sends the `dd-llmobs-enabled: true` header, as the Console does, and its `ant` install instructions drop the outdated macOS `xattr` step
- Updated the bundled dataviz skill to advise printing y-axis tick labels in full under 10,000, and horizontal ones in full under a million where they fit
- Updated the bundled dataviz skill to answer donut and pie chart requests with ranked bars or a segmented bar that prints its values
- Changed Claude's file tools to ask before editing the local copy of your organization's server-managed settings, as they do for your settings files
- Changed `/ultrareview` to check workspace trust before it runs git, as `claude ultrareview` does
- Changed the Bash tool's shell to clear any inherited `which` alias or function and to stop passing exported `which`/`unsetenv` functions to commands, so `which` is the system command or zsh builtin
- Changed `/permissions` Recently blocked to refuse approving a call you can't read in full, including one the terminal is too short to show
- Changed auto mode in Cowork cloud sessions: a hook's allow of an MCP tool call now counts as no answer, so the classifier or a permission prompt decides
- Changed hook `if` conditions such as `Monitor(tail *)` to match the Monitor tool's shell commands as `Bash(tail *)` matches Bash's
- Changed the `claude-api` skill to ask to read a Managed Agents workflow run's workflow before changing the agent to improve that run
- Changed flagged requests to retry on another model, not end in a refusal, when `ANTHROPIC_DEFAULT_OPUS_MODEL`, `availableModels` or `deniedModels` leaves only an older Opus model, or none
- Changed idle compaction to also run for subscribers with telemetry turned off, and on Bedrock, Vertex, Foundry and LLM gateways once the one-hour prompt cache is on
- Changed `FORCE_HYPERLINK=false` (also `no` and `off`) to turn hyperlinks off instead of on
- macOS: Changed `git grep` in most commands that Claude runs to use the C locale, to avoid a reported memory leak in macOS's regex library on files that aren't valid UTF-8
- [VSCode] Fixed "Clear authentication" for MCP servers reporting success when the saved sign-in could not be removed
- [VSCode] Fixed missing spinner and Stop button while a queued message's hooks run
- [VSCode] Fixed session group changes that cannot be saved, such as a delete, failing silently; an error notification now appears
- [VSCode] Fixed Cmd+F / Ctrl+F not opening the find widget in the plan preview tab
- [VSCode] Fixed the voice dictation shortcut (Ctrl+D) doing nothing under non-Latin keyboard layouts such as Russian, Greek or Hebrew
- [VSCode] Fixed missed one-time saved scheduled tasks being deleted without asking when the extension opened without a chat
- [VSCode] Changed `CLAUDE_CODE_DISABLE_CFC_PROMPT` to also stop the extension adding the Claude in Chrome instructions to a session's messages; the browser tools stay available
- [Cloud sessions] Added an Include completed button to the Scheduled tasks page when finished one-off tasks are the only ones hidden, so you can show them without opening the Sort menu
- [Cloud sessions] Fixed recently used self-hosted environments never appearing among the recent environments on the new session card
- [Cloud sessions] Fixed cloud sessions reporting uncommitted changes every turn after Claude moved a branch to a commit it had pushed from another worktree
- [Cloud sessions] Fixed the self-hosted environment details dialog in admin settings squeezing its content out of view in very short windows or at high zoom; the dialog now scrolls
- [Cloud sessions] Fixed the permission mode picker staying on Auto after a running cloud or Remote Control session refused the switch; it now shows the mode in use and tells you
- [Cloud sessions] Improved scheduled tasks: runs in Anthropic's cloud now load the plugins enabled on your claude.ai account
- [Cloud sessions] Improved Test connection for GitHub Enterprise in admin settings to also connect the way cloud sessions do, and to warn you when that second test fails
- [Cloud sessions] Improved cloud session transcripts: a rename row now names the new title, and repository and environment lists show as a table instead of one line of JSON
- [Cloud sessions] Changed cloud sessions from the web, desktop and mobile apps to start even when a setup script exits with an error, instead of failing to start
- [Remote Control] Fixed the permission mode button in Remote Control sessions showing the wrong mode until you typed; while your computer is online it now shows the real mode on open
- [Claude Tag] Added a dismissible link to the Claude Tag API docs on the Bundles and Channels tabs in admin settings, for Enterprise organizations with Slack connected
- [Claude Tag] Fixed `@Claude !restart` giving up after one failed workspace check in channels shared across Enterprise Grid workspaces; it now retries, then asks you to run it again
- [Claude Tag] Fixed a second confirmation DM and channel note when you connect your Claude account from Slack twice from the same link within a few minutes
- [Claude Tag] Fixed follow-up messages in Slack showing no sign of progress while Claude's session waits for a self-hosted runner; Claude now posts a wait notice in the thread
- [Claude Tag] Fixed Claude sometimes not answering a tag in its own thread in Slack Connect channels where both organizations have installed Claude
- [Claude Tag] Fixed Retry on plugin and skill pages in Claude Tag admin settings discarding unsaved access changes after a failed load; your edits now stay in place
- [Claude Tag] Fixed the repositories control in Claude Tag admin settings showing the same action twice; its menu now lists only what the button doesn't already do

## 2.1.312

- Added `oidc.user_id_claim` to the Claude apps gateway, to identify people by an id_token claim other than `sub`, such as Microsoft Entra ID's `oid`
- Added click to send: in fullscreen, clicking the "to send now" hint under a queued message sends it right away, as its key does
- Fixed managed settings and organization policy not being fetched for the rest of the session after signing in from the VS Code extension
- Fixed Claude overwriting a very large CLAUDE.md, rules file or @-included file in a subdirectory after seeing only its start; Write now asks Claude to read it all or edit in place
- Fixed per-directory and `paths:` skills not being found after a Bash `cd` deeper into a git repository
- Fixed a rare case where the first reply after resuming a session in the terminal could be missing the next time the session was resumed
- Fixed a command with an invalid name stopping all commands from loading, which could leave `claude -p` with no output
- Fixed the Read tool sometimes failing on PDF pages with "pdftoppm failed: Could not write image" when the clean-up of old session files ran at the same time
- Fixed the spinner, OpenTelemetry `effort` values and transcripts naming a newly picked effort level during a task before the model applied it; they now show the level in force
- Fixed the `/model` and `/effort` cache warning saying the re-read waits for your next message; a change made while Claude is working can trigger it sooner
- Fixed some sessions showing as waiting on you when the last message only mentioned items waiting on you mid-sentence
- Fixed agent view restoring input text on the next launch after it was cleared with Ctrl+C just before exiting
- Fixed agent view reopening in shell mode after exiting with Ctrl+D from an empty `!` input
- Fixed vim mode `d`, `c` and `y` with a `gj` or `gk` count larger than the lines left deleting or copying text; like Vim, they now only move the cursor
- Fixed `/verify` showing a long description meant for Claude in `/help` and the `/` command menu instead of a short one
- Improved the prompt's effort indicator: a change made mid-task now says it may wait for your next message, and the note clears when it no longer applies
- Improved WebFetch errors in cloud sessions: a host that does not resolve is now explained as possibly outside the allowed network domains, so Claude names the host to allow
- Changed Bedrock, Vertex, Foundry and Mantle to use the shorter system prompt for model names Claude Code doesn't recognize, such as custom deployment names and inference profile ARNs, even when they front Sonnet or Haiku; set `CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT=0` to keep the full prompt
- Changed automatic model switches after a flagged message to also cover model names Claude Code doesn't recognize, such as custom deployment names; set `CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK=1` to turn them off
- Changed usage limit messages to call the 5-hour window the "5-hour limit" instead of the "session limit"
- Changed cloud sessions started from the CLI to get their names and branch names from the server
- Changed prompt and agent hooks to run at most 24 at a time per session, sub-agents included, plus at most 12 that have waited longer than their event's timeout; a `timeout` under 1 second now counts as 1 second
- Changed a subagent's `autoCompactWindow` to lower the window set by `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, where it had no effect before; it still never raises that window
- Changed OpenTelemetry `mcp_server.name` to report the real name of fixed-URL remote MCP servers declared by plugins from the official Anthropic marketplace, instead of `custom`
- Changed Claude Code to stop sending the `claude_code.safety_event` OpenTelemetry event
- [VSCode] Fixed sessions ending on a bare exit code when your organization's settings couldn't be loaded or were refused at startup; the tab now says why and offers Retry or Sign in again
- [VSCode] Changed usage limit resets to show a clock time ("Resets at 3:10 PM") and to say "5-hour limit"
- [Cloud sessions] Added an effort level to the model picker when you create or edit a routine that runs in the cloud
- [Cloud sessions] Added a Bash editor with colors, line numbers and a Copy button to the setup script box in cloud environment settings
- [Cloud sessions] Improved the step shown when Claude adds a repository to a cloud session: opening it now shows a short table of what happened instead of raw JSON
- [Cloud sessions] Fixed resending an unchanged message after a failed send in a cloud session sometimes running it twice
- [Cloud sessions] Fixed a failed cloud environment creation showing its error only as a toast outside the open dialog; it now appears inside the dialog
- [Cloud sessions] Fixed Edit in a routine's menu on the Routines page going to the routine's page without opening its edit dialog
- [Remote Control] Fixed an unarchived Remote Control session showing as working until a computer reconnected; it now shows as idle
- [Claude Tag] Improved Claude Tag's retry notice in Slack to name the model in use, or say rate limits were hit, instead of a generic API error
- [Claude Tag] Fixed a Claude Tag channel's on/off switch and agent settings falling back to workspace defaults when an older private Slack channel goes public and gets a new ID
- [Claude Tag] Fixed Claude in Slack not replying in channels whose environment has network access set to None
- [Claude Tag] Fixed Claude in Slack sometimes posting a file in the wrong thread when it was answering in another thread of the same channel
- [Code Review] Fixed Code Review reviewing an outdated commit, or none at all, when GitHub delivered a push event late; it now reviews the pull request's current commit

## 2.1.311

- Added `--hold-idle-file` and `--max-hold-min` to `self-hosted-runner`, to keep an idle session while your host reports processes it left running
- Added a tip for the Explanatory output style, shown when you ask Claude for explanations
- Fixed long freezes at startup and after reading or editing files when a CLAUDE.md file holds a very long list item
- Fixed interrupting Claude not taking effect until a timeout while an MCP server had not answered a resource read or a skill was still downloading
- Fixed standard-context sessions stopping with "Usage credits required for 1M context" when a request ran over 200K tokens; Claude Code now compacts the conversation and continues
- Fixed Write and Edit stalling for up to 5 seconds after they ran, and reporting 0 lines changed, when changing thousands of lines in a file
- Fixed subagents being unable to use MCP tools from servers that finish connecting after the subagent starts
- Fixed Claude seeing stale MEMORY.md and CLAUDE.md content right after automatic compaction when those files were edited earlier in the session
- Fixed `claude -p` and SDK sessions saving transcript messages out of order or keeping messages that were taken back
- Fixed `SubagentStop` hooks running about twice a minute for each running subagent instead of once when it finishes
- Fixed the @ file picker ignoring `.ignore`/`.rgignore` negation rules that re-include git-ignored files
- Fixed a subagent's isolated worktree being removed while a background subagent it started was still working in it
- Fixed background agents in auto mode that wait on their own shells starting a new main conversation turn on every wake
- Fixed the Bash tool description claiming the working directory always persists between calls
- Fixed the environment block naming a shell commands don't run in, such as fish when the Bash tool uses zsh
- Fixed `claude mcp add`, `claude mcp remove` and `/mcp` naming the current folder instead of the project entry in `~/.claude.json` that holds a local-scope server when run below a repository root
- Fixed `claude mcp list` and `claude mcp get` showing the error code twice on failed-connection lines (for example `ENOENT: ENOENT: …`)
- Fixed Remote Control sessions staying on "Connecting" for about two minutes when a network proxy blocks a startup request
- Fixed messages that Claude sends to a cloud or Remote Control session appearing as your own message in the Claude mobile apps
- Fixed Claude not being told the cause when a file attached to a message sent over Remote Control or to a cloud session could not be saved because the disk was full, or that a message's attachments past the first 20 were left out
- Fixed WebFetch and WebSearch hanging on a stalled response in Cowork cloud sessions; an unfinished request now fails after 300 seconds
- Fixed a background session that crashed between turns not being restarted while it was attached, pinned, or had a scheduled task or wake-up set
- Fixed the "background service did not respond" error suggesting the disabled `claude daemon restart`; it now suggests `claude daemon stop --any` and says it ends background sessions
- Fixed `claude respawn
` starting the background service before reporting that no background session matches the id
- Fixed `/effort` not warning about a prompt cache miss in plan mode when the plan model differs from the session model
- Fixed `/ide` saying the VS Code extension was installed before the install finished or when it failed
- Fixed the Write tool's file preview skipping rows and miscounting hidden lines when a line is wider than the terminal
- Fixed ↑ in an agent's chat tab recalling a message that was still waiting to be delivered, so resending it sent a second copy
- Fixed Cowork cloud sessions losing their connectors and most tools after a restart when a plugin or your settings named an `agent`; Cowork cloud sessions now ignore that setting
- Fixed agent teams sessions showing an empty task list when coming back with `--resume`, `--continue`, `/resume` or `--session-id`, including after `/clear` or a crash, and `/branch` writing to the original session's list
- Fixed pasting text that mentions an image file, such as `! open /tmp/shot.png` or `/review look at /tmp/shot.png`, attaching the image and dropping its path from the prompt
- Fixed the feedback draft card showing its 1/2/0 and Esc shortcuts while the prompt has text, when those keys act on the prompt instead of the card
- Fixed a lone backslash in quotes or brackets, like `"\"` or `(\)`, disappearing from Claude's responses
- Fixed agent teammates compacting their history when `DISABLE_COMPACT` is set
- Fixed the rewind menu offering "Summarize from here" and "Summarize up to here" when `DISABLE_COMPACT` is set
- Fixed a finished `/code-review`, or another skill that runs in a sub-agent, running a second time when a cloud or background session restarts
- Fixed long hidden thinking being cut off as idle on Google Vertex AI, Microsoft Foundry and Claude Platform on AWS, where the endpoint sends thinking progress updates
- Fixed `/ide` saying it had installed the JetBrains plugin when nothing was installed
- Fixed Claude Pro and Max subscribers being told to ask their admin when their subscription can't be used; the message now points to billing settings
- Fixed the diff pane opening by itself after an edit in wide fullscreen terminals when it had nothing to show
- Fixed `/mcp` showing a remote server as failed after "Clear authentication" when the server works without sign-in
- Fixed `/mcp` showing "authenticated" for a remote server that Claude Code sends no credentials to
- Fixed a `--plugin-dir` folder of plugins loading as one plugin when an empty `.mcp.json` was at its top
- Fixed `/usage` never showing large prompt-cache misses under "What's contributing to your limits usage?"
- Fixed status line links staying plain text in background sessions after you open them from a terminal that supports links
- Fixed the /rewind confirmation saying the conversation "will be forked" when the later messages are removed from the conversation
- Fixed the /rewind warning that wrongly said manual and Bash edits are never affected by a code restore
- Fixed plan approval in screen reader mode sending feedback you had dismissed with Escape
- Fixed Claude Code retrying requests the API marked not to retry, which could hold a turn for minutes or, in unattended retry mode (`CLAUDE_CODE_RETRY_WATCHDOG`), indefinitely
- Linux: Fixed sandboxed Bash commands failing with `bwrap: Can't create file` when a `--plugin-dir` folder was also an added directory and `permissions.blockReadsOutsideWorkingDirectories` was on
- Self-hosted runner: Fixed a session failing to start when a rate limit (HTTP 429, or a git wrapper that exits 75) blocks an added read-only repository; it now starts without that repository
- Improved startup time for Pro and Max accounts by skipping two network requests on launches within an hour of the last check
- Improved `/teleport` and `claude --teleport` to warn when a compacted cloud session loads from its last compaction, so the messages it summarized aren't in the local copy
- Improved the messages shown when a background session's process exits: they no longer promise a restart that isn't coming, and they say how to resume the session
- Improved artifacts with several views: Claude now routes each view on the link's `#name` and no longer says the address bar stays the same as you switch views
- Improved shell commands that reach their timeout: the result now shows the output so far and says the command is still running in the background
- Improved compaction: when the model's reply has no summary in it, Claude Code now usually asks for the summary once more before it replaces the conversation
- Improved the Artifact tool's choice between a page and a document: explainers and visual or interactive work become artifact pages; documents are for writing people keep editing or pass around
- Improved startup time for launches whose only arguments are options and their values, such as `claude --model opus`
- Improved the "Connection dropped" API error: it now says where to look first (the proxy or gateway in use, else VPN or firewall; Anthropic API only, Bedrock, Vertex and Foundry are unchanged)
- Improved screen reader mode: deleting a rule in /permissions says "Deleted allow rule …" right away
- Improved the message shown when a pasted sign-in code is refused: it now says the code may have expired or been used, and to sign in again
- Improved Slack connector sends: Claude now checks a channel's topic for posting rules before messaging a channel you didn't name
- Improved screen reader mode: Claude's questions are listed as "Questions: Color (answered), Pages", without arrows or symbols
- Changed `ultrathink` in the interactive terminal to run its turn at xhigh effort on Opus 5.5, Sonnet 5.5, Haiku 5.5 and Fable 5.1 through Anthropic's API; typed while Claude is working, it raises the rest of that turn
- Changed the `ultrathink` rainbow to appear only where the keyword can raise effort, and not when the word is quoted or part of a file path
- Changed Ctrl+D in agent view to match the prompt: on an empty input, pressing it twice exits
- Changed `--output-format json` and `stream-json` output to write DEL, C1 control and Unicode format characters inside strings as `\uXXXX` escapes; parsed values are unchanged
- Changed model names and IDs to drop the `[1m]` suffix and its label on models where the suffix has no effect; the suffix is still accepted
- Changed startup warnings about permission rules in settings files to show once per user until the rule changes
- Changed `/code-review` to tell Claude to put the effort level first and use max only when asked
- Changed `DISABLE_COMPACT` in settings files and in a mod's `$.env.set` so they can only turn compaction off, not back on
- Changed Claude Code on Bedrock, Mantle, Vertex, and Foundry to load model settings from a signed file on downloads.claude.ai; set CLAUDE_CODE_MODEL_CATALOG=off to turn this off
- Changed sessions that set `CLAUDE_CODE_SYNC_SKILLS` with feature-flag fetching off to reuse a claude.ai skills list up to 10 minutes old that another session on the machine fetched
- Changed clicks on scrollbar arrows and bars in fullscreen lists to act when the mouse button is released, so moving off the scrollbar before letting go cancels the click
- Changed `claude purge` to say it deletes data only on this computer, not anything stored by Anthropic
- [VSCode] Added syntax coloring to code blocks in Claude's replies, in light, dark and high contrast dark themes
- [VSCode] Added a "Running UserPromptSubmit hooks" spinner status and screen reader announcement for slow UserPromptSubmit hooks
- [VSCode] Fixed custom skills and custom slash commands sent from the VS Code or JetBrains panel leaving out the open file or selected lines that ordinary messages include (anthropics/claude-code#102799)
- [VSCode] Fixed the extension host freezing while the login shell ran its start-up files to read PATH on macOS and Linux
- [VSCode] Fixed clicking an image in a tool result, or closing its preview, also opening the result's text in an editor tab
- [VSCode] Fixed voice dictation continuing to record after a message was sent with the Send button; sending now stops dictation first, as pressing Enter already did
- [VSCode] Changed the extension to start Claude Code sessions with `DISABLE_TELEMETRY` set while VS Code's telemetry setting is off, so they send no usage metrics or error reports and fetch no feature flags
- [VSCode] Changed the session list side bar to load Web sessions when the Web tab is first opened, not at startup
- [Cloud sessions] Fixed routines in Anthropic-hosted environments staying locked after their owner left the organization and rejoined; the owner can now turn them back on
- [Cloud sessions] Fixed a failed routine API token delete or regenerate showing nothing if the edit dialog had already closed; it now shows an error toast
- [Cloud sessions] Fixed cloud environment dialogs, including the admin dialog, accepting duplicate names; they now refuse a name another listed environment already has
- [Claude Tag] Added a Skills view to Claude Tag analytics showing how often Claude runs each attached skill in Slack channels and which go unused, with Usage links in admin settings
- [Claude Tag] Improved Claude Tag routines that run in a new session: a run with nothing to report can now end without posting a throwaway message to the channel
- [Claude Tag] Changed Claude Tag admin settings to show a lock instead of # for private Slack channels that your own Slack account can see
- [Code Review] Improved Code Review's check run to say no further automatic review will start when the model still can't analyze a change on the automatic retry
- [Code Review] Improved Code Review reliability: a review whose session fails to start because of a transient server fault is now retried once automatically, and its check run says so

## 2.1.310

- Added the Monitor tool and plugin monitors on Bedrock, Vertex, and Foundry, and when telemetry or nonessential traffic is disabled; long foreground sleeps are now blocked there too
- Fixed requests failing behind some gateways and compatible servers that reject the `effort-2025-11-24` beta value or mid-conversation system messages; Claude Code now retries without them
- Fixed background cleanup deleting some recent files, such as pasted images, when `cleanupPeriodDays` is set to a very large value
- Fixed compaction after a "Prompt is too long" error keeping too much of a conversation with dense text, such as base64 or SVG, so the next request could fail again
- Fixed file read permission prompts not showing where a symbolic link leads
- Fixed a question's auto-continue timeout firing the moment the external editor closed after a long edit
- Windows: Fixed PreToolUse and PermissionRequest hooks letting a tool call through when Git Bash is missing and the hook's command is only quoted strings, such as a quoted path
- Improved auto mode's prompt before the first read outside the working directories: it now says when blocking those reads makes shell commands ask for permission
- Improved memory use of non-interactive sessions (`-p`, Agent SDK) during compaction when the transcript file is very large
- Improved a mod's `Image` to draw inside tmux with `allow-passthrough` and `focus-events` on, in kitty, Ghostty, and iTerm2 3.5+ with fullscreen rendering, where it showed only its `alt` text
- Linux: Improved `/sandbox` and the sandbox startup warning to name Ubuntu's AppArmor restriction on user namespaces, and how to lift it, when it keeps bubblewrap from starting the sandbox
- Changed the error for an MCP tool call that times out in a non-interactive session while the server's elicitation is unanswered: it now tells Claude that no answer came and not to repeat the call
- [VSCode] Fixed pressing Enter on the plan review card's "Send feedback and keep planning" button approving the plan instead of sending your comments back
- [VSCode] Fixed the panel showing "Something went wrong" after "Switch branch & continue" on a cloud session opened from Session history's Web tab
- [Cloud sessions] Added Claude Code cloud sessions and Remote Control permissions to Enterprise custom roles, so Owners can control access to each by role
- [Cloud sessions] Added a Choose file button to load a cloud environment's setup script from a file
- [Cloud sessions] Fixed failed saves and archives in the cloud environment edit dialog showing no error inside the dialog
- [Cloud sessions] Fixed failed routine API token actions showing only a toast; the error now appears in the routine edit dialog
- [Cloud sessions] Improved the session start checklist to show a cloud environment's setup script output in a scrolling box
- [Cloud sessions] Changed turning on Cloud sessions or Remote Control in admin settings to ask for confirmation and list the custom roles that have that permission
- [Cloud sessions] Changed the cloud environment dialog to open network access, setup script and environment variables from rows instead of listing every editor at once
- [Claude Tag] Fixed Claude Tag treating `!` commands such as `!restart` and `!help` as ordinary messages when sent in bold, italic or strikethrough
- [Claude Tag] Fixed Claude Tag admin channel and workspace pages being replaced by a load error when a background refresh of the bundle list fails
- [Claude Tag] Fixed Claude Tag's spend limits page in admin settings reporting that no channels match a filter while channel names are still loading
- [Code Review] Fixed the Code Review admin section hiding its repositories and switches after a failed refresh of the repository list
- [Code Review] Improved the Code Review admin section to retry the first load and show one Try again banner when it still fails

## 2.1.309

- Fixed sandboxed Bash commands on macOS and Linux running the shell's startup files outside the sandbox before each command
- Fixed macOS sandbox `denyWrite` glob patterns not applying at a path's real location when the pattern's folder is reached through a symlink
- Fixed sandboxed commands and auto-accepted edits being able to modify the MCP config file passed with `--mcp-config`
- Fixed a disabled MCP server being reconnected by a later permission prompt in print and SDK sessions
- Fixed the Bash permission check trusting a variable set by a command whose redirect can fail to open
- Fixed Bash permission checks not prompting for some compound commands that change directory before running git when the `cd` is wrapped or prefixed, as they do for a plain `cd`
- Fixed an `Edit(path)` deny rule not blocking a Bash redirect to that path in some commands that also held a subshell
- Fixed worktree-isolated sessions accepting some locale-prefixed commands the isolation guard should refuse
- Fixed worktree-isolated sessions on zsh accepting some arithmetic commands that the isolation guard should refuse
- Fixed worktrees and branch checkouts that Claude Code creates so they ignore git replace refs, as its other git operations already do
- Fixed profile store write protection not applying when the config directory is reached through a symlink
- Fixed sessions compacting repeatedly aft
