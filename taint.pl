#!/usr/bin/perl -T

use strict;
use warnings;

# $ENV{PATH} = '/usr/bin:/bin';  # Safe, minimal PATH

print "Enter a filename to list (e.g., /tmp): ";
my $input = <STDIN>;
chomp($input);

# We're using tainted data directly in a system call — this will trigger an error in taint mode
print "Attempting to list files in: $input\n";
system("ls", "-l", $input);

