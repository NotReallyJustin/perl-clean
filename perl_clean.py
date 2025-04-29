import re

# Note: cwd will always be the user's cwd

# ---- Util Functions -----------
def find_split_idx(perl_line:str, split_char:str) -> int:
    '''
    Finds the first valid character we can use to split a string with
    @param perl_line The line of perl code to find the first char of
    @param split_char The character you want to use to split the line of code
    @returns the index of that valid split char
    '''
    
    assert split_char != "'", "You can't split with a quote"
    assert split_char != '"', "You can't split with a quote"
    assert split_char != "\\", "You can't split with a backslash"
    
    in_quotes = False
    escaped = False
    
    for i in range(len(perl_line)):
        char = perl_line[i]

        # Check for unescaped ' or " 
        # Don't worry about having something like 'b" because that's a syntax error.
        # If code doesn't run to begin with, there's no point of running taint analysis
        if char == "'" or char == '"':
            in_quotes = not in_quotes
            
        if char == "\\":
            escaped = not escaped   # Not directly setting this to true because \\ --> we're no longer in escaped territory
            
        if char == split_char and (not in_quotes) and (not escaped):
            return i        # We found it!
        
        # At the very end, if we are escaped and the current character is not another \, we're good
        if escaped and char != "\\":
            escaped = False
        
    return len(perl_line)   # If we find nothing, the whole string is fine

def filter_comments(perl_line:str) -> str:
    '''
    Eliminates all comments from a line of Perl code
    @param perl_line The line of perl code to rid comments from
    @returns the line of perl code without comments
    '''
    # Get rid of Perl comments by getting rid of chars after unescaped and unquoted #s
    split_idx = find_split_idx(perl_line, "#")
    return perl_line[0:split_idx]

# ---- Perl file processing -------
def decompose_code(perl_path:str) -> list[tuple[int, str]]:
    '''
    Breaks a .pl file into independent lines of code we can process later as a list. Also gets rid of comments.
    @param perl_path Path to perl file
    @returns A list of perl code. Each element in the list is in the form of a tuple --> (line #, perl code)
    '''
    read_output = []
    with open(perl_path) as file:
        read_output = file.readlines()
    
    # Now process the read_output to get rid of comments (and more)
    perl_lines = []
    
    for line_num in range(len(read_output)):
        unparsed = read_output[line_num]
        
        code = filter_comments(unparsed)
        
        # Sometimes, people will do things like "$arg = shift; $hid = $arg . 'bar';" all on one line
        # Break them up into seperate lines. The good news is that Perl code must end in a semicolon
        
        while code != '':
            semicolon_idx = find_split_idx(code, ";")
            parsed = code[0: semicolon_idx + 1].strip() # Include the semicolons & get rid of whitespace
            
            # Don't append empty strings (like EOF)
            if parsed != "":
                perl_lines.append((line_num + 1, parsed))   
            
            # You will always find a semicolon in a line of Perl code. So that + 1 will eventually lead you to ""
            code = code[semicolon_idx + 1:] 
            
    return perl_lines

# A really good way to test decompose_code is by having it parse ./test_clean.pl
# Check if the list output makes sense
# print(decompose_code('./test_clean.pl'))

# ----- Handling variables ------------
def extract_vars(perl_line:str) -> list[str]:
    '''
    Extracts all variables from a line of Perl code.
    @param perl_line The line of perl code to extract
    @returns all variables in the line of perl code
    '''
    
    '''
    Extracts all variables
    
    Perl makes it easy for us since variables must start with a sigil ($@%&*). The language pioneered this concept actually.
    The programmer can't bypass this or else the Perl interpreter breaks. They're forced to follow this regular expression below.
    Also what characters can go in a variable name is very heavily restricted so this makes it easy for us too
    '''
    # Get rid of comments again in case someone forgot to do it earlier
    code = filter_comments(perl_line)
    
    # Now, find the perl variables inside the actual code (not comments!)
    perl_vars_regexp = r"[\$\@\%\&\*][a-zA-Z_][a-zA-Z0-9_]*"
    return re.findall(perl_vars_regexp, code)

# # These are very good test strings to see if extract_vars is working correctly
# # Should return ['$arg', '$arg2', '$arg3']
# print(extract_vars('$arg = shift;	\\#	$arg2 . "and a string with # inside $arg3" # $arg4 is tainted'))

# # Should return ['$sudo', '$cat', '$etcpasswd']
# print(extract_vars('exec "sh -c $sudo $cat # $etcpasswd" # $sillyvarnoonecaresabout'))

def map_variables(perl_lines:list[tuple[int, str]]) -> dict[str, list[int]]:
    '''
    Creates a dictionary w/ variable names --> lines in the code
    @param perl_lines All the perl code, split into a nice list by `decompose_code()`
    @returns A dictionary that maps all variables to the line they are on
    '''
    mapping = dict()
    
    for (line_num, code) in perl_lines:
        variables_in_curr_line = extract_vars(code)
        
        for variable in variables_in_curr_line:
            
            if variable in mapping:
                mapping[variable] += [line_num]
            else:
                # If there's no entry in mapping yet, make a list in the mapping with their line in it
                mapping[variable] = [line_num]
    
    return mapping
            
# A good way to test map_variables to once again, run it on `./test_clean.pl`
print(map_variables(decompose_code("./test_clean.pl")))
    
# ---- Main processing code ------
def main():
    pass

# Command Line Interface