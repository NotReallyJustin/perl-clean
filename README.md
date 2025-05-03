# perl-clean
Automated tool to completely and verbosely run perlsec taint analysis on Perl Code

# Dependencies
* Perl's Scalar::Util feature. Install this via `$cpan Scalar::Util`

# Taint Script (WIP)
```perl
use Scalar::Util qw(tainted); say STDERR "delinstart"; tainted($file) ? say STDERR "tainted" : say STDERR "untainted"; tainted($new_owner) ? say STDERR "tainted" : say STDERR "untainted"; tainted($mode) ? say STDERR "tainted" : say STDERR "untainted"; say STDERR "delinend";
```