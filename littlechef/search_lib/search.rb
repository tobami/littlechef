#
# Copyright 2011, edelight GmbH
#
# Authors:
#       Markus Korn <markus.korn@edelight.de>
#       Seth Chisamore <schisamo@opscode.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

if Chef::Config[:solo]

  # add currrent dir to load path
  $: << File.dirname(__FILE__)

  # All chef/solr_query/* classes were removed in Chef 11; Load vendored copy
  # that ships with this cookbook
  $: << File.expand_path("vendor", File.dirname(__FILE__)) if Chef::VERSION.to_i >= 11

  # Ensure the treetop gem is installed and available
  begin
    require 'treetop'
  rescue LoadError
    run_context = Chef::RunContext.new(Chef::Node.new, {}, Chef::EventDispatch::Dispatcher.new)
    Chef::Resource::ChefGem.new("treetop", run_context).run_action(:install)
  end

  require 'search/overrides'
  require 'search/parser'

  module Search; class Helper; end; end

  # The search and data_bag related methods moved form `Chef::Mixin::Language`
  # to `Chef::DSL::DataQuery` in Chef 11.
  if Chef::VERSION.to_i >= 11
    module Chef::DSL::DataQuery
      def self.included(base)
        base.send(:include, Search::Overrides)
      end
    end
    Search::Helper.send(:include, Chef::DSL::DataQuery)
  else
    module Chef::Mixin::Language
      def self.included(base)
        base.send(:include, Search::Overrides)
      end
    end
    Search::Helper.send(:include, Chef::Mixin::Language)
  end

  class Chef
    class Search
      class Query
        def initialize(*args)
        end
        def search(*args, &block)
          ::Search::Helper.new.search(*args, &block)
        end
      end
    end
  end
end
