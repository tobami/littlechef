#
# Copyright 2011, edelight GmbH
#
# Authors:
#       Markus Korn <markus.korn@edelight.de>
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
#  based on Brian Akins's patch:
#    http://lists.opscode.com/sympa/arc/chef/2011-02/msg00000.html
#

if Chef::Config[:solo]

  class Chef
    module Mixin
      module Language
        # Hook into Chef which reads all items in a given `bag` and converts
        # them into one single Hash
        def data_bag(bag)
          @solo_data_bags = Mash.new if @solo_data_bags.nil?
          unless @solo_data_bags[bag]
            @solo_data_bags[bag] = Mash.new
            data_bag_path = Chef::Config[:data_bag_path]
            Dir.glob(File.join(data_bag_path, bag, "*.json")).each do |f|
              item = JSON.parse(IO.read(f))
              @solo_data_bags[bag][item['id']] = Mash.new(item)
            end
          end
          @solo_data_bags[bag].keys
        end

        # Hook into Chef which returns the ruby representation of a given
        # data_bag item
        def data_bag_item(bag, item)
          data_bag(bag) unless ( !@solo_data_bags.nil? && @solo_data_bags[bag])
          @solo_data_bags[bag][item]
        end

      end
    end
  end
  
end
