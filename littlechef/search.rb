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

if Chef::Config[:solo]
  
  if (defined? require_relative).nil?
    # defenition of 'require_relative' for ruby < 1.9, found on stackoverflow.com
    def require_relative(relative_feature)
      c = caller.first
      fail "Can't parse #{c}" unless c.rindex(/:\d+(:in `.*')?$/)
      file = $`
      if /\A\((.*)\)/ =~ file # eval, etc.
        raise LoadError, "require_relative is called in #{$1}"
      end
      absolute = File.expand_path(relative_feature, File.dirname(file))
      require absolute
    end
  end
  
  require_relative 'data_bags.rb'
  
  # Checks if a given `value` is equal to `match`
  # If value is an Array, then `match` is checked against each of the value's
  # members, and true is returned if any of the members matches.
  # The comparison is string based, means: if value is not an Array then value
  # gets converted into a string (using .to_s) and then checked.
  def match_value(value, match)
    if value.is_a?(Array)
      return value.any?{ |x| match_value(x, match) }
    else
      return value.to_s == match
    end
  end
        
  # Factory function to parse the query string into a `Query` object
  # Returns `nil` if the query is not supported.
  def make_query(query)
    if query.nil? or query === "*:*"
      return NilQuery.new(query)
    end
    
    query.gsub!("[* TO *]", "*")
    if query.count("()") == 2 and query.start_with?("(") and query.end_with?(")")
      query.tr!("()", "")
    end
    
    if query.include?(" AND ")
      return AndQuery.new(query.split(" AND ").collect{ |x| make_query(x) })
    elsif query.include?(" OR ")
      return OrQuery.new(query.split(" OR ").collect{ |x| make_query(x) })
    elsif query.include?(" NOT ")
      return NotQuery.new(query.split(" NOT ").collect{ |x| make_query(x) })
    end
      
    if query.start_with?("NOT")
      negation = true
      query = query[3..-1]    # strip leading NOT
    else
      negation = false
    end
    
    if query.split(":", 2).length == 2
      field, query_string = query.split(":", 2)
      if query_string.end_with?("*")
        return WildCardFieldQuery.new(query, negation)
      else
        return FieldQuery.new(query, negation)
      end
    else
      return nil
    end
  end
  
  # BaseClass for all queries
  class Query
    def initialize( query )
      @query = query
    end
    
    def match( item )
      return false
    end
  end
  
  # BaseClass for all queries with AND, OR or NOT conditions
  class NestedQuery < Query
    def initialize( conditions )
      @conditions = conditions
    end
  end
  
  # AndQuery matches if all sub-queries match
  class AndQuery < NestedQuery
    def match( item )
      return @conditions.all?{ |x| x.match(item) }
    end
  end
  
  # NotQuery matches if the *leftmost* condition matches, but the others don't
  class NotQuery < NestedQuery
    def match( item )
      base_condition = @conditions[0]
      last_conditions = @conditions[1..-1] || []
      return base_condition.match(item) & last_conditions.all?{ |x| !x.match(item) }
    end
  end
  
  # OrQuery matches if any of the sub-queries match
  class OrQuery < NestedQuery
    def match( item )
      return @conditions.any?{ |x| x.match(item) }
    end
  end
  
  # NilQuery always matches
  class NilQuery < Query
    def match( item )
      return true
    end
  end
    
  # FieldQuery looks for a certain attribute in the item to match and checks
  # the value of this attribute for equality.
  # If `negation` is true the oposite result will be returned.
  class FieldQuery < Query
    def initialize( query, negation=false )
      @field, @query = query.split(":", 2)
      @negation = negation
      @field.strip!
    end
    
    def match( item )
      value = item[@field]
      if value.nil?
        result = false
      end
      result = match_value(value, @query)
      if @negation
        return !result
      else
        return result
      end
    end
  end
    
  # WildCardFieldQuery is exactly like FieldQuery, but allows trailing stars.
  # Instead of checking for exact matches it just checks if the value begins
  # with a certain string, or (in case of an Array) any of its items value
  # begins with a string.
  class WildCardFieldQuery < FieldQuery
    
    def initialize( query, negation=false )
      super
      @query = @query.chop
    end
    
    def match( item )
      value = item[@field]
      if value.nil?
        result = false
      elsif value.is_a?(String)
        if value.strip().empty?
          result = true
        else
          result = value.start_with?(@query)
        end
      else
        result = value.any?{ |x| x.start_with?(@query) }
      end
      if @negation
        return !result
      else
        return result
      end
    end
  end

  class Chef
    class Recipe
      
      # Overwrite the search method of recipes to operate locally by using
      # data found in data_bags.
      # Only very basic lucene syntax is supported and also sorting the result
      # is not implemented, if this search method does not support a given query
      # an exception is raised.
      # This search() method returns a block iterator or an Array, depending
      # on how this method is called.
      def search(bag_name, query=nil, sort=nil, start=0, rows=1000, &block)
        if !sort.nil?
          raise "Sorting search results is not supported"
        end
        @_query = make_query(query)
        if @_query.nil?
          raise "Query #{query} is not supported"
        end
        if block_given?
          pos = 0
        else
          result = []
        end
        data_bag(bag_name.to_s).each do |bag_item_id|
          bag_item = data_bag_item(bag_name.to_s, bag_item_id)
          if @_query.match(bag_item)
            if block_given?
              if (pos >= start and pos < (start + rows))
                yield bag_item
              end
              pos += 1
            else
              result << bag_item
            end
          end
        end
        if !block_given?
          return result.slice(start, rows)
        end
      end
    end
  end

end
