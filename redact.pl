#!/usr/bin/perl

# Must sanitize this if calling system
# $ENV{PATH} = '/usr/bin:/bin';  # Safe, minimal PATH

# Check for arguments
die "-----\nThis program makes a file only accessible by a given user\nUsage: $0 <file> <username>\n--------\n" unless @ARGV == 2;

my ($file, $new_owner) = @ARGV;

# Check if file exists
die "Error: File '$file' does not exist.\n" unless -e $file;

# Change file permissions
my $mode = 0700;

$owner = $new_owner;
chmod $mode, $file or die "Failed to chmod '$file': $!\n";

# Change file owner
system("chown $owner $file;");

# Get results
# To exploit this, run as SUID/SGID and pass in something like /etc/shadow
# Or just command injection this
print "File '$file' has been successfully redacted!\n";