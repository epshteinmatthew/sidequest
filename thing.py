def sort(list):
    list2 = list.copy()
    for item in list:
        smaller = 0
        for jdem in list:
            if(jdem < item):
                smaller+=1
        list2[smaller] = item
    return list2

print(sort([1,2,3,5,9,6,8,7]))