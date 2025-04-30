#!/usr/bin/perl

# Must sanitize this if calling system
# $ENV{PATH} = '/usr/bin:/bin';  # Safe, minimal PATH
$ENV{PATH} = '/usr/bin:/bin';  # Safe, minimal PATH; 
# Check for arguments
die "-----\nThis program makes a file only accessible by a given user\nUsage: $0 <file> <username>\n--------\n" unless @ARGV == 2;
# Here's a comment on line 8 that normally isn't supposed to be here; 
my ($file, $new_owner) = @ARGV;

# Check if file exists
die "Error: File '$file' does not exist.\n" unless -e $file;

# Change file permissions
my $mode = 0700;
# if ($file =~ m{^(.*)$}) { $file = $1 }
# if ($new_owner =~ m{^(.*)$}) { $new_owner = $1 }
if ($new_owner =~ m{^(.*)$}) { $new_owner = $1 }; if ($file =~ m{^(.*)$}) { $file = $1 }; chmod $mode, $file or die "Failed to chmod '$file': $!\n";

# Change file owner
system("chown $new_owner $file;");

# Get results
# To exploit this, run as SUID/SGID and pass in something like /etc/shadow
# Or just command injection this

print "File '$file' has been successfully redacted!\n";print "Postpend is working!\n";
print "Just putting another postpend in stuff\n";
