// Recover a missing pull request even when publishing the staged tree was a no-op.
import flag
import os

type Command = fn (string, []string) !string

struct Request {
	repo    string
	branch  string
	version string
}

struct CommandLog {
mut:
	actions []string
}

fn run_command(executable string, args []string) !string {
	result := os.execute(os.quoted_path(executable) + ' ' + args.map(os.quoted_path(it)).join(' '))
	if result.exit_code != 0 {
		return error('${executable} failed (${result.exit_code}): ${result.output.trim_space()}')
	}
	return result.output.trim_space()
}

fn open_proposal(request Request, run Command) ! {
	if request.repo == '' || request.branch == '' || request.version == '' {
		return error('DEPLOY_TARGET_REPO, BRANCH_NAME, and RELEASE_VERSION are required')
	}
	if run('git', ['write-tree'])! == run('git', ['rev-parse', 'origin/master^{tree}'])! {
		println('Generated files already match master; no proposal needed.')
		return
	}
	mut lookup := ['pr', 'list', '--repo', request.repo, '--base', 'master', '--head', request.branch]
	lookup << ['--state', 'open', '--json', 'number', '--jq', '.[0].number // empty']
	existing := run('gh', lookup)!
	if existing != '' {
		println('Using existing pull request #${existing} without modifying it')
		return
	}
	body :=
		'Automated bindings generated from KhronosGroup/Vulkan-Docs tag `${request.version}`. ' +
		"Once merged, this registry snapshot is available from the target module's master branch. " +
		'Package release tags follow the semantic version in `v.mod` and are created separately.'
	result := run('gh', ['pr', 'create', '--repo', request.repo, '--base', 'master', '--head',
		request.branch, '--title', 'Generated bindings ${request.version}', '--body', body])!
	if result != '' {
		println(result)
	}
}

fn fixture(existing string, unchanged bool) ![]string {
	mut history := &CommandLog{}
	request := Request{
		repo:    'fixture/module'
		branch:  'generated/v1.4.366'
		version: 'v1.4.366'
	}
	run := fn [mut history, request, existing, unchanged] (executable string, args []string) !string {
		if executable == 'git' {
			if args == ['write-tree'] && !unchanged {
				return 'candidate'
			}
			return 'base'
		}
		assert executable == 'gh'
		assert args.contains(request.repo) && args.contains(request.branch)
		assert args.contains('master')
		history.actions << args[..2].join(' ')
		if args[..2] == ['pr', 'list'] {
			assert args.contains('open')
			return existing
		}
		assert args[..2] == ['pr', 'create']
		assert args.contains('Generated bindings ${request.version}')
		return ''
	}
	open_proposal(request, run)!
	return history.actions
}

fn run_cli() ! {
	mut parser := flag.new_flag_parser(os.args[1..])
	parser.application('open_generated_proposal')
	parser.description('Open a missing PR for a generated Vulkan binding tree.')
	test := parser.bool('self-test', 0, false, 'exercise proposal recovery without using GitHub')
	if parser.bool('help', `h`, false, 'show help') {
		println(parser.usage())
		return
	}
	if parser.finalize()!.len != 0 {
		return error('unexpected positional arguments')
	}
	if test {
		assert fixture('80', false)! == ['pr list']
		assert fixture('', false)! == ['pr list', 'pr create']
		assert fixture('', true)!.len == 0
		println('Generated proposal recovery fixtures passed.')
		return
	}
	open_proposal(Request{
		repo:    os.getenv('DEPLOY_TARGET_REPO')
		branch:  os.getenv('BRANCH_NAME')
		version: os.getenv('RELEASE_VERSION')
	}, run_command)!
}

run_cli() or {
	eprintln(err)
	exit(1)
}
