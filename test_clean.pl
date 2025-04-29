# Expected behavior:
# decomposed code == [(4, '$hi = 4;'), (4, '$bye = 7;'), (4, '$michael = 14;'), (4, '$brainrot = "Tun Tun Tun Tun Tun Tun Sahur";'), (5, 'print("My favorite Italian brainrot is $brainrot;\\n");')]
# ---
# When you map, expected output is: {'$hi': [5], '$bye': [5], '$michael': [5], '$brainrot': [5, 6]}
$hi = 4; $bye = 7; $michael = 14; $brainrot = "Tun Tun Tun Tun Tun Tun Sahur";  # Random comment ; ; ; ; ; ; 
print("My favorite Italian brainrot is $brainrot;\n");      # Random comment to test ; parsing ; ; ; \; ; more ;