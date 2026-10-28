#!/usr/bin/bash

# UWB MPI Cluster Setup Script
# Haram Kwon, 2019

# Generate SSH key
ssh-keygen -N "" -f $HOME/.ssh/id_rsa 

# Trust all host fingerprints in cluster
for N in {1..24};
do
    ssh-keyscan -H cssmpi${N}.uwb.edu >> $HOME/.ssh/known_hosts;
    ssh-keyscan -H cssmpi${N} >> $HOME/.ssh/known_hosts;
done;

# Add generated SSH key to trusted key list
cat $HOME/.ssh/id_rsa.pub >> $HOME/.ssh/authorized_keys
chmod 600 $HOME/.ssh/authorized_keys
