/* Insert your model definition here */

/**
* Name: District4
* Based on the internal empty template. 
* Author: nnktr
* Tags: 
*/


model District4lockdown

/* Insert your model definition here */


	
global {
	file shape_file_roads <- file("../includes/District4/Road_Network.shp");
	file shape_file_buildings <- file("../includes/District4/Building.shp");
	file shape_file_bounds <- file("../includes/District4/Boundary.shp");
	geometry shape <- envelope(shape_file_bounds);
	float step <- 10 #mn;
	date starting_date <- date("2019-09-01-00-00-00");	
	int nb_people <- 100;
	int min_work_start <- 6;
	int max_work_start <- 8;
	int min_work_end <- 16; 
	int max_work_end <- 20; 
	float min_speed <- 1.0 #km / #h;
	float max_speed <- 5.0 #km / #h; 
	float destroy <- 0.02;
	int repair_time <- 2 ;
	graph the_graph;
	list<road> remain_road;
	map<road,float> weights_map;
	
	init {
		create road from: shape_file_roads with: [District::string(read("District"))];
		create building from: shape_file_buildings with: [type::string(read ("TypeCode"))] {
			if type="HTKT" {
				color <- #blue ;
			}
		}
		weights_map <- road as_map (each:: (each.destruction_coeff * each.shape.perimeter));
		the_graph <- as_edge_graph(road) with_weights weights_map;
		
		list<road> roads1 <- road where (each.District="District 1");
		list<road> roads7 <- road where (each.District="District 7");
		create people number: nb_people {
			speed <- rnd(min_speed, max_speed);
			start_work <- rnd (min_work_start, max_work_start);
			end_work <- rnd(min_work_end, max_work_end);
			living_place <- one_of(roads1) ;
			working_place <- one_of(roads7) ;
			objective <- "resting";
			location <- any_location_in (living_place); 
		}
	}
	
	reflex update_graph{
		weights_map <- road as_map (each:: (each.destruction_coeff * each.shape.perimeter));
		the_graph <- the_graph with_weights weights_map;
	}
	reflex repair_road when: every(repair_time #hour ) {
		list<road> the_road_to_repair <- road where (each.destruction_coeff > 1.5) ;
		ask the_road_to_repair {
			self.destruction_coeff <- 1.0 ;
		}
	}
	
	action mouse_click {
		list<road> selected_roads <- road overlapping(circle(30) at_location #user_location);
		ask selected_roads{
			self.wei <- 100.0;
			self.is_closed <- !self.is_closed;
			remain_road <- road where (each.is_closed = false);
			weights_map <- remain_road as_map (each:: (each.destruction_coeff * each.shape.perimeter));
			the_graph <- as_edge_graph(remain_road) with_weights weights_map;
		}
	}
}

species building {
	string type;
	rgb color <- #gray  ;
	
	aspect base {
		draw shape color: color ;
	}
}

species road  {
	string District;
	float wei <- 1.0;
	bool is_closed <- false;
	//float destruction_coeff <- rnd(1.0,2.0) max: 2.0;
	float destruction_coeff <- 1.0;
	int colorValue <- int(255*(destruction_coeff - 1)) update: int(255*(destruction_coeff - 1));
	rgb color <- rgb(min([255, colorValue]),max ([0, 255 - colorValue]),0)  update: is_closed ? #red : rgb(min([255, colorValue]),max ([0, 255 - colorValue]),0) ;
	
	aspect base {
		draw shape color: color width:2;
	}
}

species people skills:[moving] {
	rgb color <- #yellow ;
	road living_place <- nil ;
	road working_place <- nil ;
	int start_work ;
	int end_work  ;
	string objective ; 
	point the_target <- nil ;
		
	reflex time_to_work when: current_date.hour = start_work and objective = "resting"{
		objective <- "working" ;
		the_target <- any_location_in (working_place);
	}
		
	reflex time_to_go_home when: current_date.hour = end_work and objective = "working"{
		objective <- "resting" ;
		the_target <- any_location_in (living_place); 
	} 
	 
	reflex move when: the_target != nil {
		weights_map <- road as_map (each::each.shape.perimeter * each.wei);
		path path_followed <- goto(target:the_target, on:the_graph, move_weights: weights_map, return_path: true, recompute_path: true);
		
		list<geometry> segments <- path_followed.segments;
		loop line over: segments {
			float dist <- line.perimeter;
			ask road(path_followed agent_from_geometry line) { 
				destruction_coeff <- destruction_coeff + (destroy * dist / shape.perimeter);
				//wei <- wei+0.1;
			}
		}
		if the_target = location {
			the_target <- nil ;
		}
	}
	
	// Draw people by a circle
	aspect base {
		draw circle(10) color: color border: #black;
	}
}

experiment road_traffic type: gui {
	parameter "Shapefile for the roads:" var: shape_file_roads category: "GIS" ;
	parameter "Shapefile for the bounds:" var: shape_file_bounds category: "GIS" ;
	parameter "Number of people agents" var: nb_people category: "People" ;
	parameter "Earliest hour to start work" var: min_work_start category: "People" min: 2 max: 8;
	parameter "Latest hour to start work" var: max_work_start category: "People" min: 8 max: 12;
	parameter "Earliest hour to end work" var: min_work_end category: "People" min: 12 max: 16;
	parameter "Latest hour to end work" var: max_work_end category: "People" min: 16 max: 23;
	parameter "minimal speed" var: min_speed category: "People" min: 0.1 #km/#h ;
	parameter "maximal speed" var: max_speed category: "People" max: 10 #km/#h;
	parameter "Value of destruction when a people agent takes a road" var: destroy category: "Road" ;
	parameter "Number of hours between two road repairs" var: repair_time category: "Road" ;
	
	output {
		display city_display type:opengl {
			species building aspect: base ;
			species road aspect: base ;
			species people aspect: base ;
			event mouse_down action:mouse_click;
		}
		display chart_display refresh: every(10#cycles) { 
			chart "Road Status" type: series size: {1, 0.5} position: {0, 0} {
				data "Mean road destruction" value: mean (road collect each.destruction_coeff) style: line color: #green ;
				data "Max road destruction" value: road max_of each.destruction_coeff style: line color: #red ;
			}
			chart "People Objectif" type: pie style: exploded size: {1, 0.5} position: {0, 0.5}{
				data "Working" value: people count (each.objective="working") color: #magenta ;
				data "Resting" value: people count (each.objective="resting") color: #blue ;
			}
		}
	}
}