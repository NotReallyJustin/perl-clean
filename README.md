# perl-clean
Automated tool to completely and verbosely run perlsec taint analysis on Perl Code. <br /> <br />
CS810 Project by Justin Chen and Dan Liu <br />
![Screenshot 2025-05-09 012919](https://github.com/user-attachments/assets/0dfd6a51-18f3-449c-84f1-025c5fc93dee)

## Overview
The Perl interpreter has a built-in (albeit optional) security tool for developers called perlsec that conducts taint analysis on Perl files during runtime and halts execution when a potentially tainted variable is going to cause a side-effect. However, perlsec isn’t as detailed, comprehensive, and verbose as modern taint analysis tools and as such, isn’t very useful to Software Developers, AppSec Engineers, and Threat Hunters. <br />

Perl-Clean solves this problem! It builds off perlsec, and turns that module into a functioning static/dynamic analysis tool.

## Dependencies
* Perl's Scalar::Util feature. Install this via `$cpan Scalar::Util`
