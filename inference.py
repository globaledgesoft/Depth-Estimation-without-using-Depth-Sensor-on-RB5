from __future__ import absolute_import, division, print_function
import qcsnpe as qc
import os
import cv2
import numpy as np
import argparse
import matplotlib.pyplot as plt
import glob

ap = argparse.ArgumentParser()
ap.add_argument("-i", "--img_folder", default=None, help="image_folder")
ap.add_argument("-v", "--vid", default=None,help="cam/video_path")
args = vars(ap.parse_args())
    
im_folder_path =  args["img_folder"]
vid = args["vid"]

CPU = 0
GPU = 1
DSP = 2
AIP = 3

out_layers = np.array(["disparities/ExpandDims:0"])
model = qc.qcsnpe("models/depth_model.dlc", out_layers, CPU)

# Returns a byte-scaled image
def bytescale(data, cmin=None, cmax=None, high=255, low=0):
    if data.dtype == np.uint8:
        return data
    
    if high < low:
        raise ValueError("`high` should be larger than `low`.")
    
    if cmin is None:
        cmin = data.min()
    if cmax is None:
        cmax = data.max()
    
    cscale = cmax - cmin
    if cscale < 0:
        raise ValueError("`cmax` should be larger than `cmin`.")
    elif cscale == 0:
        cscale = 1
    
    scale = float(high - low) / cscale
    bytedata = (data * 1.0 - cmin) * scale + 0.4999
    bytedata[bytedata > high] = high
    bytedata[bytedata < 0] = 0
    return np.cast[np.uint8](bytedata) + np.cast[np.uint8](low)

# Returns a post processed image    
def post_process_disparity(disp):
    _, h, w = disp.shape
    l_disp = disp[0,:,:]
    r_disp = np.fliplr(disp[1,:,:])
    m_disp = 0.5 * (l_disp + r_disp)
    l, _ = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, h))
    l_mask = 1.0 - np.clip(20 * (l - 0.05), 0, 1)
    r_mask = np.fliplr(l_mask)
    return r_mask * l_disp + l_mask * r_disp + (1.0 - l_mask - r_mask) * m_disp


# Returns a preprocessed image
def pre(input_image): 
   
    input_image = cv2.resize(input_image, (512,256), interpolation=cv2.INTER_LANCZOS4)
    disp = model.predict(input_image)
    out=disp["disparities/ExpandDims:0"]
    out=np.reshape(out,(2,256,512))     
    disp_pp = post_process_disparity(np.array(out,dtype=np.float32))
    disp_pp = bytescale(disp_pp)
    disp_to_img = cv2.resize(disp_pp, (640, 480))
    return  disp_to_img 

# main function will save result as depth estimated image and video format
def main():

    if vid == None and im_folder_path == None:
        print("required command line args atleast ----img_folder <image folder path> or --vid <cam/video_path>")
        
    # image inference
    if im_folder_path is not None:
        for bb,file in enumerate (glob.glob(im_folder_path + '/*.jpg')):
            a= cv2.imread(file)
            input_image=cv2.cvtColor(a,cv2.COLOR_BGR2RGB)
            disp_to_img=pre(input_image)
            #writing the images in a folder output_images
            cv2.imwrite('image_folder/img{}.png'.format(bb), disp_to_img)
            plt.imsave( 'image_folder/image{}.png'.format(bb), disp_to_img, cmap='plasma')
            print('done!')

    # video inference
    else:
        if vid == "cam":
            #video_capture = cv2.VideoCapture(0)   #for webcam input
            video_capture = cv2.VideoCapture("tcp://localhost:8080")     
        else:
            video_capture = cv2.VideoCapture(vid)
                                
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        output = cv2.VideoWriter('output.mp4', fourcc, 10.0, (640, 480))  

        while (video_capture.isOpened()):
            var,frame=video_capture.read()
            if var:
                input_image=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                disp_to_img=pre(input_image)
                out_img=np.zeros((480,640,3)).astype(np.uint8)
                out_img[:,:,0]=disp_to_img
                out_img[:,:,1]=disp_to_img
                out_img[:,:,2]=disp_to_img
                                           
                output.write(np.array(out_img))
                print('done!')

                if cv2.waitKey(1) & 255==ord('q'):
                    break
            
        video_capture.release()
        output.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()

