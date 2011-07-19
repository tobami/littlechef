# based on Brian Akins's patch: http://lists.opscode.com/sympa/arc/chef/2011-02/msg00000.html
if Chef::Config[:solo]
  
  class Query
    def initialize( query )
      @query = query
    end
    
    def match( item )
      return false
    end
  end
  
  class NilQuery < Query
    def match( item )
      return true
    end
  end
    
  class FieldQuery < Query
    
    def initialize( query )
      @field, @query = query.split(":", 2)
    end
    
    def match( item )
      value = item[@field]
      result = (!value.nil? && value.include?(@query))
      return result
    end
  end
    
  class WildCardFieldQuery < FieldQuery
    
    def initialize( query )
      super      
      @query = @query.chop
    end
    
    def match( item )
      value = item[@field]
      if value.nil?
        return false
      elsif value.is_a?(String)
        return value.start_with?(@query)
      else
        return value.any?{ |x| x.start_with?(@query) }
      end
    end
  end
  
  class Chef
    module Mixin
      module Language
        def data_bag(bag)
          @solo_data_bags = {} if @solo_data_bags.nil?
          unless @solo_data_bags[bag]
            @solo_data_bags[bag] = {}
            data_bag_path = Chef::Config[:data_bag_path]
            Dir.glob(File.join(data_bag_path, bag, "*.json")).each do |f|
              item = JSON.parse(IO.read(f))
              @solo_data_bags[bag][item['id']] = item
            end
          end
          @solo_data_bags[bag].keys
        end

        def data_bag_item(bag, item)
          data_bag(bag) unless ( !@solo_data_bags.nil? && @solo_data_bags[bag])
          @solo_data_bags[bag][item]
        end

      end
    end
  end

  class Chef
    class Recipe
      def search(bag_name, query=nil, sort=nil, start=0, rows=1000, &block)
        if !sort.nil?
          raise "Sorting search results is not supported"
        end
        @_query = make_query(query)
        if @_query.nil?
          raise "Query #{query} is not supported"
        end
        if block.nil?
          result = []
        else
          pos = 0
        end
        data_bag(bag_name.to_s).each do |bag_item_id|
          bag_item = data_bag_item(bag_name.to_s, bag_item_id)
          if @_query.match(bag_item)
            if block.nil?
              result << bag_item
            else
              if (pos >= start and pos < (start + rows))
                yield bag_item
              end
              pos += 1
            end
          end
        end
        if block.nil?
          return result.slice(start, rows)
        end
      end
      
      def make_query(query)
        if query.nil? or query === "*:*"
          return NilQuery.new(query)
        elsif query.split(":", 2).length == 2
          field, query_string = query.split(":", 2)
          if query_string.end_with?("*")
            return WildCardFieldQuery.new(query)
          else
            return FieldQuery.new(query)
          end
        else
          return nil
        end
      end
    end
  end

end
