maintainer        "Opscode, Inc."
maintainer_email  "cookbooks@opscode.com"
license           "Apache 2.0"
description       "Installs subversion"
version           "0.8.4"

%w{ redhat centos fedora ubuntu debian }.each do |os|
  supports os
end

depends "apache2"

recipe "subversion", "Includes the client recipe. Modified by site-cookbooks"
recipe "subversion::client", "Subversion Client installs subversion and some extra svn libs"
recipe "subversion::server", "Subversion Server (Apache2 mod_dav_svn)"

attribute "subversion/user",
  :display_name => "Subversion user",
  :description => "Name of subversion user to use for checkout",
  :default => "subversion"

attribute "subversion/password",
  :display_name => "Subversion password",
  :description => "Password for the subversion user to use for checkout",
  :default => "subversion"

attribute "subversion/repo_name",
  :display_name => "Subversion repository name",
  :description => "Name of the subversion repository",
  :default => "repo"

attribute "subversion/server_name",
  :display_name => "Subversion server name",
  :description => "Name for the subversion server to use for checkout",
  :default => "svn"

attribute "subversion/repo_dir",
  :display_name => "Subversion Repo directory",
  :description => "Path where the svn checkout will be made",
  :default => "/srv/svn2"
