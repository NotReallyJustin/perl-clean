#!/usr/bin/perl
use strict;
use warnings;

my $filepath = shift;          # TAINTED!!! This uses user specified input

# TAINTED! Writing to this file is a side-effect
if ($filepath eq "")
{
    # This is to prove that a normal if statement is not enough to qualify as "sanitizing" anything for perlsec
    $filepath = "/tmp/system.log";
}

my $file;
open($file, '>>', $filepath) or die "Could not open '$filepath': $!\n";

# Write timestamp
print $file "--- Logged at:", scalar localtime, " ---\n";

# Log Hostname
my $hostname = `hostname`;
chomp($hostname);
print $file "Hostname: $hostname\n";

# Log Uptime
my $uptime = `uptime`;
chomp($uptime);
print $file "Uptime: $uptime\n";

# Log Disk usage
my $disk = `df -h /`;
print $file "Disk Usage:\n$disk\n";

close($file);
