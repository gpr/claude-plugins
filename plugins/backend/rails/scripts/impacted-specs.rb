#!/usr/bin/env ruby
# Lists RSpec files impacted by a change to <file>.
# Includes: the direct spec, specs referring to the file's constant,
# and (for concerns) specs for models that `include` the concern.
# Output: one spec path per line on stdout. Missing paths logged on stderr.

require 'pathname'
require 'set'
require 'shellwords'

def die(msg)
  warn "impacted-specs: #{msg}"
  exit 1
end

changed = ARGV[0] or die 'usage: impacted-specs.rb <changed-file>'
path = Pathname.new(changed)
die "not a ruby file: #{changed}" unless path.extname == '.rb'

def constant_for(path)
  rel = path.to_s
  stripped = rel.sub(%r{\Aapp/[^/]+/}, '').sub(%r{\Alib/}, '').sub(/\.rb\z/, '')
  stripped.split('/').map { |seg| seg.split('_').map(&:capitalize).join }.join('::')
end

def direct_spec(path)
  case path.to_s
  when %r{\Aspec/.*_spec\.rb\z} then path.to_s
  when %r{\Aapp/[^/]+/(.*)\.rb\z} then "spec/#{Regexp.last_match(1)}_spec.rb"
  when %r{\Alib/(.*)\.rb\z}      then "spec/lib/#{Regexp.last_match(1)}_spec.rb"
  end
end

def rg_files(pattern, *globs)
  return [] unless system('command -v rg >/dev/null 2>&1')
  out = `rg --files-with-matches --fixed-strings -- #{pattern.shellescape} #{globs.map(&:shellescape).join(' ')} 2>/dev/null`
  out.split("\n").reject(&:empty?)
end

impacted = Set.new
if (direct = direct_spec(path))
  if File.exist?(direct)
    impacted << direct
  else
    warn "no direct spec at #{direct}"
  end
end

const = constant_for(path)
impacted.merge(rg_files(const, 'spec'))

if path.to_s.start_with?('app/models/concerns/')
  including_models = rg_files("include #{const}", 'app/models').map do |f|
    direct_spec(Pathname.new(f))
  end.compact.select { |p| File.exist?(p) }
  impacted.merge(including_models)
end

puts impacted.sort
