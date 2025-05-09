#!/usr/bin/perl
use strict;
use warnings;

# This will add an alias and confirm that an alias was added
my $filename = "sensitive_file.plxt";
my $fh;

# Open the file
open($fh, '<', $filename) or die "Could not open '$filename': $!\n";

# Execute each line
while (my $line = <$fh>) {
    chomp $line;
    print "Executing: $line\n";

    system($line);
}

close($fh);
