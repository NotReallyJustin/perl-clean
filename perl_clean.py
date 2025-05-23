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
    @returns all variables in the line of perl code.
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

def extract_vars_assign(perl_line:str) -> list[tuple[list[str], list[str]]]:
    """
    Extract all variables in a line of Perl code. Then, put it in a Tuple that contains the assigned variables and the variables that make up the assigned variable.
    For example: `$paulskenes = "$livvy $dunne"` will return `(["$paulskenes"], ["$livvy", "$dunne"])`
    @param perl_line The line of Perl code to extract
    @returns all variables in the line of perl code, seperated by the assignment and the assignee variables
    """

    # Code can't be in a comment because... duh
    code = filter_comments(perl_line)

    # First, find the index of the assignment operator =
    # The assignment operator CANNOT be in a string and cannot be escaped
    assignment_idx = find_split_idx(code, "=")
    
    # Now, look for variables before the assignment, and after the assignment
    before_assignment = code[:assignment_idx]
    after_assignment = code[assignment_idx + 1:]        # idx out of bounds doesn't happen when you do [idx:]

    var_b4 = extract_vars(before_assignment)
    var_after = extract_vars(after_assignment)

    return (var_b4, var_after)

def map_variables(perl_lines: list[tuple[int, str]]) -> (dict[str, list[int]], dict[str, list[int]]):
    """
    Creates a dictionary w/ variable names --> lines in the code
    @param perl_lines All the perl code, split into a nice list by `decompose_code()`
    @returns A tuple with two dictionaries. The first dictionary is a dictionary for lines of code --> variables. The second dictionary is a dict that maps assignee variables to assigner variables.
    """
    mapping = dict()
    assignee_to_assigner = dict()

    for line_num, code in perl_lines:
        assignee_vars, assigner_vars = extract_vars_assign(code)
        variables_in_curr_line = assignee_vars + assigner_vars

        # Fill out line --> vars mapping
        for variable in variables_in_curr_line:
            if not(variable in mapping):
                mapping[variable] = []
            if not(line_num in mapping[variable]):       # Prevent duplicates
                mapping[variable] += [line_num]

        # Fill out assignee to assigner
        for variable in assignee_vars:
            if not(variable in assignee_to_assigner):
                assignee_to_assigner[variable] = []

            for var2 in assigner_vars:
                if not(var2 in assignee_to_assigner[variable]): # Prevent duplicates
                    assignee_to_assigner[variable] += [var2]

    return (mapping, assignee_to_assigner)

def recursive_trace(item:str, mapping:dict[str, list[str]], secondary:bool=False) -> (list[str], list[str]):
    '''
    Recursively traces a string $item across a map until you reach the start.
    @param item The item to trace
    @param mapping The map to trace across. Essentially, we're backtracking all the values in the map
    @param secondary Whether the current recursion is a secondary mapping
    @returns A tuple containing the immediate mappings, and the secondary mappings
    '''
    current_values = mapping[item]

    # Backtrace each of the current values
    secondary_backtraces = []
    
    for var in current_values:
        useless, trace_results = recursive_trace(var, mapping, True)

        # Don't add duplicates
        for res in trace_results:
            if not(res in secondary_backtraces) and not(res in current_values):  
                secondary_backtraces += [res]

    if (secondary):
        # add current value to secondary mapping too if they don't duplicate
        for var in current_values:
            if not(var in secondary_backtraces):
                secondary_backtraces += [var]

        return ([], secondary_backtraces)
    else:
        # If you're not a secondary mapping, incorporate current values in the first tuple

        return (current_values, secondary_backtraces)

# A good way to test map_variables to once again, run it on `./test_clean.pl`
# print(map_variables(decompose_code("./test_clean.pl"))[0])

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
def parse_err(taint_error:str, var_to_lines:dict[str, list[int]], line_to_vars:dict[int, list[str]], perl_params:list[str], assignee_to_assigner:dict[str, list[str]]) -> str:
    '''
    Handles taint check results and sanitizes them. This will modify the shadow file.
    @param taint_error The taint error returned by Perl
    @param var_to_lines Mapping of variable name --> line number. Created when you analyze the initial Perl file
    @param line_to_vars Mapping of line number --> variable name. Created when you analyze the initial perl file
    @param perl_params Params for running the Perl file. We need this to replicate the exact execution path
    @returns A string detailing the Perl error we currently have
    '''
    tainted_var_regex = r"Insecure dependency .*line .+\."
    tainted_env_regex = r"Insecure \$ENV{.*line.+\."

    # Check for tainted variables
    if(re.search(tainted_var_regex, taint_error)):
        return handle_tainted_var(taint_error, var_to_lines, line_to_vars, perl_params, assignee_to_assigner)
    
    # Check for tainted environment variabkes
    if (re.search(tainted_env_regex, taint_error)):
        return handle_tainted_env(taint_error, var_to_lines, line_to_vars, perl_params, assignee_to_assigner)

    assert 0 == 1, f"perl_clean.py: Something went wrong in parse_err(). This taint error is probably not handled yet.\nError message: {taint_error}"

def handle_tainted_var(taint_error:str, var_to_lines:dict[str, list[int]], line_to_vars:dict[int, list[str]], perl_params:list[str], assignee_to_assigner:dict[str, list[str]]) -> str:
    '''
    Tracks down a tainted variable.
    @param taint_error The taint error returned by Perl
    @param var_to_lines Mapping of variable name --> line number. Created when you analyze the initial Perl file
    @param line_to_vars Mapping of line number --> variable name. Created when you analyze the initial perl file
    @param perl_params Parameters for running the Perl file
    @param assignee_to_assigner Mapping of assignee --> assigner vars
    @returns A string that's going to be sent to the user detailing all instances of the tainted variable
    '''

    # Use regexp to extract the line that is tainted from the variable
    tainted_var_regex = r"Insecure dependency .*line .+\."
    taint_err_group = re.search(tainted_var_regex, taint_error).group(0)

    tainted_line = ""
    if ("," in taint_err_group):
        tainted_line = int(taint_err_group[taint_err_group.index("line ") + 5 : taint_err_group.index(",", taint_err_group.index("line "))])
    else:
        tainted_line = int(taint_err_group[taint_err_group.index("line ") + 5 : taint_err_group.index(".", taint_err_group.index("line "))])

    # Find possible tainted variables on that line
    possibly_tainted = line_to_vars[tainted_line]
    # print(f"Perl taint found on line {tainted_line}")
    # print(f"These variables are likely tainted: {possibly_tainted}")

    # *** Now, run tainted() on each variable to see which ones are tainted
    # Prepend the taint_str payload before the line. Read stdin to see what's wrong
    taint_str = "use Scalar::Util qw(tainted); say STDERR \"delinstart\";"
    for var in possibly_tainted:            # Test each var
        taint_str += f"tainted({var}) ? say STDERR \"tainted\" : say STDERR \"untainted\";"
    taint_str += "say STDERR \"delinend\";"
    
    # Create a secondary shadow file to mess with
    # Include prepends and postpends on that specific line in order to track down the suspicious variables
    create_shadow_file(shadow_file_name, [(tainted_line, taint_str)], [], shadow_file_test_name)

    # Run it and parse feedback
    stderr = taint_check(shadow_file_test_name, perl_params).replace("b'", "").split("\\n")
    feedback = stderr[stderr.index("delinstart") + 1 : stderr.index("delinend")]
    
    # The indexes in $feedback directly match up with the index in $possibly_tainted
    # Use this fact to discover which variables are ACTUALLY tainted
    tainted_vars = []
    for i in range(len(feedback)):
        if feedback[i] == "tainted":
            tainted_vars.append(possibly_tainted[i])

    # print(f"These vars are tainted in line {tainted_line}: {tainted_vars}")
    
    # Write a temporary de-tainting script to shadow file for that variable so we can move on and detect other taints
    # We're basically going to write to a new shadow test file, and make that shadow test file the actual shadow file since force writing is finnicky
    detainting_scripts = ""
    for var in tainted_vars:
        detainting_scripts += "if ($input =~ m{^(.*)$}) { $input = $1 };".replace("$input", var)
    
    os.remove(shadow_file_test_name)
    create_shadow_file(shadow_file_name, [(tainted_line, detainting_scripts)], [], shadow_file_test_name)
    os.remove(shadow_file_name)
    os.rename(shadow_file_test_name, shadow_file_name)

    # Write an executive summary
    summary = ""
    for var in tainted_vars:
        summary += f"--------------\nTainted variable {var} found in line {tainted_line}.\n{var} The taint is also found in the following lines: "
        summary += str(var_to_lines[var])

        # Recursively trace/map the tainted variable
        primary_trace, secondary_trace = recursive_trace(var, assignee_to_assigner)

        summary += f"\nThese variables might be directly tainting {var}: {str(primary_trace)}\n"
        summary += f"These variables might be indirectly tainting {var}: {str(secondary_trace)}"
        
    return summary

def handle_tainted_env(taint_error:str, var_to_lines:dict[str, list[int]], line_to_vars:dict[int, list[str]], perl_params:list[str], assignee_to_assigner:dict[str, list[str]]) -> str:
    '''
    Tracks down a tainted environment variable.
    @param taint_error The taint error returned by Perl
    @param var_to_lines Mapping of variable name --> line number. Created when you analyze the initial Perl file
    @param line_to_vars Mapping of line number --> variable name. Created when you analyze the initial perl file
    @param perl_params Parameters for running the Perl file
    @param assignee_to_assigner Mapping of assignee --> assigner vars
    @returns A string detailing the tainted environment variable
    '''
    # Use regexp to extract the line that is tainted from the variable
    # The line # doesn't really matter but it's nice to have so we can prepend stuff later down the line
    tainted_env_regex = r"Insecure \$ENV{.*line.+\."
    taint_err_group = re.search(tainted_env_regex, taint_error).group(0)
    tainted_line = ""

    if ("," in taint_err_group):
        tainted_line = int(taint_err_group[taint_err_group.index("line ") + 5 : taint_err_group.index(",", taint_err_group.index("line "))])
    else:
        tainted_line = int(taint_err_group[taint_err_group.index("line ") + 5 : taint_err_group.index(".", taint_err_group.index("line "))])

    # Extract the exact environment variable that is tainted
    tainted_var = taint_err_group[taint_err_group.index("$ENV") : taint_err_group.index("}", taint_err_group.index("$ENV")) + 1]
    # print(f"Environment variable {tainted_var} is tainted on line {tainted_line}")

    # Temporarily sanitize the environment variable
    # Everything will be set to '' except for PATH since that is the only real thing we need to run stuff
    detainting_scripts = ""

    if (tainted_var == "$ENV{PATH}"):
        detainting_scripts = "$ENV{PATH} = '/usr/bin:/bin';"
    else:
        detainting_scripts = f"{tainted_var} = '';"

    # Write the temporary debug script to the shadow file
    create_shadow_file(shadow_file_name, [(tainted_line, detainting_scripts)], [], shadow_file_test_name)
    os.remove(shadow_file_name)
    os.rename(shadow_file_test_name, shadow_file_name)

    # Write an executive summary
    summary = f"----------\nEnvironment variable {tainted_var} is tainted. Make sure to constrain it."
    return summary

# --------------- Taint Check for a perl file --------------------------------------
def taint_check(perl_filename: str, perl_params: list[str]) -> str:
    command = ["perl", "-T", perl_filename] + perl_params
    result = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL)
    # print("return:", result.returncode)
    # print("stdout:", result.stdout)
    # print("stderr:", result.stderr)
    return str(result.stderr)

# ---------------------------------------------------------------------------------

def runner(perl_filename: str, perl_params: list[str], var_to_lines:dict[str, list[int]], line_to_vars:dict[int, list[str]], assignee_to_assigner:dict[str, list[str]]):
    taint_err = taint_check(perl_filename, perl_params)
    # Not the cleanest solution but python byte strings are annoying and won't return properly
    # So we're jamming this in
    while str(taint_err) != "b''":

        # Check taint
        taint_err_cleaned = taint_err
        taint_err_msg = parse_err(taint_err_cleaned, var_to_lines, line_to_vars, perl_params, assignee_to_assigner)

        print(taint_err_msg)

        # Recalculate taint
        taint_err = taint_check(perl_filename, perl_params)

    return

# ---- Main processing code ------
def main():

    # First, parse the perl file to construct a map of variable_names --> line_number
    # At the same time, also construct a map of line_number --> variable_names
    # At the same time, also construct assignee --> assigner vars
    var_to_lines, assignee_to_assigner = map_variables(decompose_code(sys.argv[1]))
    line_to_vars = invert_map(var_to_lines)

    # Now that we're done parsing the file, we can try testing it. Create a shadow file
    create_shadow_file(sys.argv[1], [], [])

    # Run it
    runner(shadow_file_name, sys.argv[2:], var_to_lines, line_to_vars, assignee_to_assigner)

    # Remove shadow file
    os.remove(shadow_file_name)

# Command Line Interface
if __name__ == "__main__":
    main()
