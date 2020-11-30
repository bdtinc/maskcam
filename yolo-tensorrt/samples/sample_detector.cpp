#include "class_timer.hpp"
#include "class_detector.h"

#include <memory>
#include <thread>

int main()
{
	Config config_v4_tiny;
	config_v4_tiny.net_type = YOLOV4_TINY;
	config_v4_tiny.detect_thresh = 0.5;
	config_v4_tiny.file_model_cfg = "../../yolo/facemask-yolov4-tiny.cfg";
	config_v4_tiny.file_model_weights = "../../yolo/facemask-yolov4-tiny_best.weights";
	config_v4_tiny.inference_precison = FP16;

	std::unique_ptr<Detector> detector(new Detector());
	detector->init(config_v4_tiny);
	cv::Mat image0 = cv::imread("../configs/dog.jpg", cv::IMREAD_UNCHANGED);
	cv::Mat image1 = cv::imread("../configs/person.jpg", cv::IMREAD_UNCHANGED);
	std::vector<BatchResult> batch_res;
	Timer timer;
	for (int lap = 0; lap < 10; lap++)
	{
		//prepare batch data
		std::vector<cv::Mat> batch_img;
		cv::Mat temp0 = image0.clone();
		cv::Mat temp1 = image1.clone();

		// Set .cfg to batch=4
		batch_img.push_back(temp0);
		batch_img.push_back(temp1);
		batch_img.push_back(temp0);
		batch_img.push_back(temp1);

		//detect
		timer.reset();
		detector->detect(batch_img, batch_res);
		timer.out("detect");

		//disp
		for (int i = 0; i < batch_img.size(); ++i)
		{
			for (const auto &r : batch_res[i])
			{
				std::cout << "batch " << i << " id:" << r.id << " prob:" << r.prob << " rect:" << r.rect << std::endl;
				cv::rectangle(batch_img[i], r.rect, cv::Scalar(255, 0, 0), 2);
				std::stringstream stream;
				stream << std::fixed << std::setprecision(2) << "id:" << r.id << "  score:" << r.prob;
				cv::putText(batch_img[i], stream.str(), cv::Point(r.rect.x, r.rect.y - 5), 0, 0.5, cv::Scalar(0, 0, 255), 2);
			}
			cv::imwrite("image" + std::to_string(i) + ".jpg", batch_img[i]);
			// cv::imshow("image"+std::to_string(i), batch_img[i]);
		}
		// cv::waitKey(10);
	}
}
