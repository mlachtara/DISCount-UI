We aim to implement a website allowing for these functions:
1. A limited upload of images to a cloud storage site.
2.(Optional) training of a new YOLO or alternative models. Talk with Omar about this. Mentioned different varieties of models being potentiall more performany given image parameters.
3. Upload a .pt/ computer vision model to be used in the DISCount pipeline.
4. Some sort of job creation where we can store image counts
5. Show the uploaded images to the use following tiling for discrete human labelling
6. Easy to use labelling system.
7. Tying the human labels with the pts proposal distribution for the purpose of generating an estimate.
8. A graph showing the estimated number of objects vs the number of labelled tiles. Similarly show the standard error. First graph should be noisier and converge on a number eventually. Second graph should approach 0.
9. Should link to the research or give credit to initial authors.
10. (Optional)Export to excel or something would be cool.


Run Instructions:
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env   # edit as needed
# then open .env and paste in the two Azure values from you
# aka the connection string and name
python run.py

# Frontend (separate terminal)
cd frontend
npm install
npm run dev





# then open .env and paste in the two Azure values from you




TODO:
Need to change the username password database to be in azure/ long term solution

Need to send the job data to the database/ long term solution

Need to implement rate limits with this. Consider running model on azure?

Need to label the other domains

Need to deploy.

Need to make a video explaining the process.

Need to fix the YOLO detector training system. Possibly roll it all together?

