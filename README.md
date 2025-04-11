# mke_garbage_recycling
A Home Assistant custom integration for the city of Milwaukee, WI to pull next garbage and recycling dates. 

## Overview
This module is written with the help of reference documents and Google Gemini 2.5 AI. It did a decent job taking my existing PowerShell API script and changing it into Python and HA compatible code. I am intending to use this to create a automation at home that lets me know to get my sleepy butt up and run stuff out to the curb before the garbage men notice I am awake. The reason for that is if there is any chance they know I am awake they will speed dash my neighborhood and miss all my junk. I hope this helps you too.

## Technical Stuff
There is not much to this. I basically watch calls to the [milwaukee.gov trash collection website](https://city.milwaukee.gov/sanitation/GarbageRecyclingSchedules) and replicated it. This looks to be the same thing the MKE Mobile app does as well. The module is set to update once every 6 hours, which is likely excessive, but not likely for me to get banned. I also went the extra mile and made it so HA prompts you to add your address in native HA UI instead of having to modify a JSON file. 

## Feedback
I would love to have any if anyone has any advice on how to make this more functional. 
