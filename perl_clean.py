import re
import sys
import os
import argparse
import subprocess

shadow_file_name = "perl_clean_shadow.pl"           # This one is used in the runner
shadow_file_test_name = "perl_clean_test.pl"        # This one is used by the error parsers to figure out the exact errors we're dealing with

# Note: cwd will always be the user's cwd

# ---- Util Functions -----------
def find_split_idx(perl_line: str, split_char: str) -> int:
    """
    Finds the first valid character we can use to split a string with
    @param perl_line The line of perl code to find the first char of
    @param split_char The character you want to use to split the line of code
    @returns the index of that valid split char
    """

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
            escaped = not escaped  # Not directly setting this to true because \\ --> we're no longer in escaped territory

        if char == split_char and (not in_quotes) and (not escaped):
            return i  # We found it!

        # At the very end, if we are escaped and the current character is not another \, we're good
        if escaped and char != "\\":
            escaped = False

    return len(perl_line)  # If we find nothing, the whole string is fine


def filter_comments(perl_line: str) -> str:
    """
    Eliminates all comments from a line of Perl code
    @param perl_line The line of perl code to rid comments from
    @returns the line of perl code without comments
    """
    # Get rid of Perl comments by getting rid of chars after unescaped and unquoted #s
    split_idx = find_split_idx(perl_line, "#")
    return perl_line[0:split_idx]

def invert_map(map: dict[str, list[int]]) -> dict[int, list[str]]:
    '''
    Inverts/Reverses a map by swapping the indexes and values.
    For example, {"$hi": [1], "$bye": [1, 2]} --> {1: ["$hi"], 2: ["$hi, bye"]}
    @params map The map to reverse
    @returns The reversed map
    '''
    reversed_map = dict()

    for key, value_list in map.items():
        for value in value_list:
            
            # If the map entry doesn't exist yet, create one and set the value to an empty list
            if (not (value in reversed_map)):
                reversed_map[value] = []

            # Avoid adding duplicates
            if (not (key in reversed_map[value])):
                reversed_map[value] += [key]

    # To make UI easier down the line, sort the reversed map
    # Python uses quick sort so we're good
    reversed_map = dict(sorted(reversed_map.items()))
    return reversed_map

# ---- Perl file processing -------
def decompose_code(perl_path: str) -> list[tuple[int, str]]:
    """
    Breaks a .pl file into independent lines of code we can process later as a list. Also gets rid of comments.
    @param perl_path Path to perl file
    @returns A list of perl code. Each element in the list is in the form of a tuple --> (line #, perl code)
    """
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

        while code != "":
            semicolon_idx = find_split_idx(code, ";")
            parsed = code[
                0 : semicolon_idx + 1
            ].strip()  # Include the semicolons & get rid of whitespace

            # Don't append empty strings (like EOF)
            if parsed != "":
                perl_lines.append((line_num + 1, parsed))

            # You will always find a semicolon in a line of Perl code. So that + 1 will eventually lead you to ""
            code = code[semicolon_idx + 1 :]

    return perl_lines


# A really good way to test decompose_code is by having it parse ./test_clean.pl
# Check if the list output makes sense
# print(decompose_code('./test_clean.pl'))


# ----- Handling variables ------------
def extract_vars(perl_line: str) -> list[str]:
    """
    Extracts all variables from a line of Perl code.
    @param perl_line The line of perl code to extract
    @returns all variables in the line of perl code
    """

    """
    Extracts all variables

    Perl makes it easy for us since variables must start with a sigil ($@%&*). The language pioneered this concept actually.
    The programmer can't bypass this or else the Perl interpreter breaks. They're forced to follow this regular expression below.
    Also what characters can go in a variable name is very heavily restricted so this makes it easy for us too
    """
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


def map_variables(perl_lines: list[tuple[int, str]]) -> dict[str, list[int]]:
    """
    Creates a dictionary w/ variable names --> lines in the code
    @param perl_lines All the perl code, split into a nice list by `decompose_code()`
    @returns A dictionary that maps all variables to the line they are on
    """
    mapping = dict()

    for line_num, code in perl_lines:
        variables_in_curr_line = extract_vars(code)

        for variable in variables_in_curr_line:
            if variable in mapping:
                mapping[variable] += [line_num]
            else:
                # If there's no entry in mapping yet, make a list in the mapping with their line in it
                mapping[variable] = [line_num]

    return mapping


# A good way to test map_variables to once again, run it on `./test_clean.pl`
# print(map_variables(decompose_code("./test_clean.pl")))

# --------------- Helper Util Functions -------------------------------------------
def create_shadow_file(perl_filepath: str, prepends: list[tuple[int, str]], postpends: list[str], filename:str=shadow_file_name) -> str:
    '''
    Creates a (cloned) shadow file with certain prepended strings in front of certain lines and postpended strings after the file
    @param perl_filepath The file path of the original file to create a clone/shadow file of
    @param prepends A list of tuples ($line, $str). Prepend $str in front of $line
    @param postpends A list of strings to add at the end of the file.
    @param filename The file name of the shadow file. By default, this is $perl_clean_shadow global var
    '''
    # Assertion check to make sure that we're not overwriting an existing shadow file
    assert not os.path.exists(filename), f"Shadow file {filename} already exists. Make sure you get rid of that."

    # Can't have something names
    # Clone the file. Split it by line
    read_output = []
    with open(perl_filepath) as file:
        read_output = file.readlines()

    # Prepend
    for (line, code) in prepends:
        # -1 because line # --> read output
        read_output_idx = line - 1

        # Seperate multiple code statements on one line with ;. 
        # If $code already has ;, nothing happens and ig Perl just executes an empty statement which doesn't hurt us
        read_output[read_output_idx] = f"{code}; {read_output[read_output_idx]}"    

    # Postpend
    read_output[:-1] += "\n"        # Add a new line to the end of the last line in the file
    for code in postpends:
        # Write_lines is funny. You need to add \n
        read_output.append(f"{code}\n")

    # Write to shadow file
    with open(filename, "w") as shadow_file:
        shadow_file.writelines(read_output)

# Here's a good check for creating shadow files.
# Looks silly, but this completely sanitizes redact.pl
# create_shadow_file("./redact.pl", [
#     (5, "$ENV{PATH} = '/usr/bin:/bin';  # Safe, minimal PATH"),
#     (8, "# Here's a comment on line 8 that normally isn't supposed to be here"),
#     (18, "if ($file =~ m{^(.*)$}) { $file = $1 }"),
#     (18, "if ($new_owner =~ m{^(.*)$}) { $new_owner = $1 }")
# ], [
#     'print "Postpend is working!\\n";',
#     'print "Just putting another postpend in stuff\\n";'
# ])

# --------------- Taint Check Functionality ---------------------------------------
def parse_err(taint_error:str, var_to_lines:dict[str, list[int]], line_to_vars:dict[int, list[str]]) -> str:
    '''
    Handles taint check results and sanitizes them. This will modify the shadow file.
    @param taint_error The taint error returned by Perl
    @param var_to_lines Mapping of variable name --> line number. Created when you analyze the initial Perl file
    @param line_to_vars Mapping of line number --> variable name. Created when you analyze the initial perl file
    @returns A string detailing the Perl error we currently have
    '''
    tainted_var_regex = r"Insecure dependency .*line .+\."

    # Check for tainted variables
    if(re.search(tainted_var_regex, taint_error)):
        handle_tainted_var(taint_error, var_to_lines, line_to_vars)

def handle_tainted_var(taint_error:str, var_to_lines:dict[str, list[int]], line_to_vars:dict[int, list[str]]) -> str:
    '''
    Tracks down a tainted variable.
    @param taint_error The taint error returned by Perl
    @param var_to_lines Mapping of variable name --> line number. Created when you analyze the initial Perl file
    @param line_to_vars Mapping of line number --> variable name. Created when you analyze the initial perl file
    @returns A string that's going to be sent to the user detailing all instances of the tainted variable
    '''

    # Use regexp to extract the line that is tainted from the variable
    tainted_var_regex = r"Insecure dependency .*line .+\."
    taint_err_group = re.search(tainted_var_regex, taint_error).group(0)
    tainted_line = int(taint_err_group[taint_err_group.index("line ") + 5 :taint_err_group.index(".", taint_err_group.index("line "))])

    # Find possible tainted variables on that line
    possibly_tainted = line_to_vars[tainted_line]
    
    # Create another shadow file to mess with
    # Include prepends and postpends on that specific line in order to track down the suspicious variables

    print(f"Perl taint found on line {tainted_line}")
    print(f"These variables are likely tainted: {possibly_tainted}")

# --------------- Taint Check for a perl file --------------------------------------
def taint_check(perl_filename: str, perl_params: list[str]) -> str:
    command = ["perl", "-T", perl_filename] + perl_params
    result = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL)
    # print("return:", result.returncode)
    # print("stdout:", result.stdout)
    # print("stderr:", result.stderr)
    return str(result.stderr)

# ---------------------------------------------------------------------------------

def runner(perl_filename: str, perl_params: list[str], var_to_lines:dict[str, list[int]], line_to_vars:dict[int, list[str]]):
    taint_err = taint_check(perl_filename, perl_params)
    while len(taint_err) != 0:

        # Check taint
        taint_err_cleaned = taint_err
        parse_err(taint_err_cleaned, var_to_lines, line_to_vars)
        
        # Recreate the shadow file with the new changes
        os.remove(shadow_file_name)
        # # create_shadow_file(shadow_file_name, [], [])

        # # Recalculate taint
        # taint_err = taint_check(perl_filename, perl_params)
        break
    return

# ---- Main processing code ------
def main():

    # First, parse the perl file to construct a map of variable_names --> line_number
    # At the same time, also construct a map of line_number --> variable_names
    var_to_lines = map_variables(decompose_code(sys.argv[1]))
    line_to_vars = invert_map(var_to_lines)

    # Now that we're done parsing the file, we can try testing it. Create a shadow file
    create_shadow_file(sys.argv[1], [], [])

    # Run it
    runner(shadow_file_name, sys.argv[2:], var_to_lines, line_to_vars)

# Command Line Interface
if __name__ == "__main__":
    main()
