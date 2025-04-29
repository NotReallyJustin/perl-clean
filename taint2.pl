#!/usr/bin/perl -T

use strict;
use warnings;

$ENV{PATH} = '/usr/bin:/bin';  # Safe, minimal PATH

print "Enter a filename to list (e.g., /tmp): ";
my $input = <STDIN>;
chomp($input);

# Taint mode will flag this as unsafe unless we "untaint" it by validating and extracting it
print "Listing files in: $input\n";
system("ls", "-l", $input);
